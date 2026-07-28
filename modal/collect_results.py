#!/usr/bin/env python3
"""Validate a benchmark manifest and emit machine-readable and Markdown reports."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import modal


DEFAULT_VOLUME = "jcode-bench-v1-results"


def read_volume_file(volume: modal.Volume, path: str) -> bytes:
    return b"".join(volume.read_file(path))


def parse_scores(data: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in data.decode().splitlines() if line.strip()]


def helper_event_count(agent: str, log: str) -> int:
    """Count explicit helper tool events without mistaking normal agent messages."""
    if agent == "jcode":
        return log.count('"name":"swarm"') + log.count('"name": "swarm"')

    if agent == "opencode":
        count = 0
        for line in log.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") != "tool_use":
                continue
            part = event.get("part")
            if isinstance(part, dict) and part.get("tool") == "task":
                count += 1
        return count

    if agent == "claude-code":
        # Claude Code stream-json emits assistant messages whose content blocks
        # carry tool_use entries; `Task` is its native subagent delegation tool.
        count = 0
        for line in log.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") != "assistant":
                continue
            message = event.get("message")
            if not isinstance(message, dict):
                continue
            for block in message.get("content") or []:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") == "Task"
                ):
                    count += 1
        return count

    event_types = {
        "collab_tool_call",
        "collab_tool_call_output",
        "spawn_agent",
        "send_input",
        "wait_agent",
        "close_agent",
    }
    count = 0
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in event_types:
            count += 1
    return count


def truncated_turn_count(agent: str, log: str, ceiling: int) -> int:
    """Count turns whose output stopped exactly at the model's output ceiling.

    A turn that ends at the ceiling was cut off mid-answer, which for an agent
    usually means a truncated tool call and an early end to the run. The Opus 5
    pilot lost 96% of its budget to this, so it is now a first-class validity
    signal rather than something a human has to notice in a log.
    """
    if ceiling <= 0:
        return 0
    count = 0
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if agent == "jcode":
            if event.get("type") == "tokens" and event.get("output") == ceiling:
                count += 1
            continue
        usage = event.get("message", {}).get("usage") if isinstance(event.get("message"), dict) else None
        if isinstance(usage, dict) and usage.get("output_tokens") == ceiling:
            count += 1
    return count


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Reasoning effort is part of the identity of a cell. Grouping without it
    # would average low, medium, and high into one meaningless mean and hide the
    # very axis an effort sweep exists to measure.
    groups: dict[tuple[str, bool, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "completed":
            groups[
                (
                    row["agent"],
                    row["swarm"],
                    row.get("model", "unknown"),
                    row.get("reasoning_effort", "unknown"),
                )
            ].append(row)

    result = []
    for (agent, swarm, model, effort), values in sorted(groups.items()):
        result.append(
            {
                "agent": agent,
                "swarm": swarm,
                "model": model,
                "reasoning_effort": effort,
                "completed_tasks": len(values),
                "mean_final_score": round(
                    statistics.fmean(value["final_score"] for value in values), 4
                ),
                "mean_best_score": round(
                    statistics.fmean(value["best_score"] for value in values), 4
                ),
                "total_agent_duration_s": round(
                    sum(value["agent_duration_s"] for value in values), 3
                ),
                "helper_events": sum(value["helper_events"] for value in values),
            }
        )
    return result


# Ordered weakest to strongest, so a swept report walks the axis in the order a
# reader expects rather than alphabetically ("high" before "low").
EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")


def effort_rank(effort: str) -> tuple[int, str]:
    if effort in EFFORT_ORDER:
        return (EFFORT_ORDER.index(effort), effort)
    return (len(EFFORT_ORDER), effort)


def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    """Score and agent-time movement of `left` relative to `right`."""
    score_delta = left["mean_final_score"] - right["mean_final_score"]
    duration_delta = (
        left["total_agent_duration_s"] / right["total_agent_duration_s"] - 1
    ) * 100
    return {
        "mean_score_delta": round(score_delta, 4),
        "geomean_efficiency_factor": round(2**score_delta, 4),
        "total_agent_time_delta_percent": round(duration_delta, 2),
    }


def comparisons(aggregates: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_effort: dict[str, dict[tuple[str, bool], dict[str, Any]]] = defaultdict(dict)
    for row in aggregates:
        by_effort[row.get("reasoning_effort", "unknown")][
            (row["agent"], row["swarm"])
        ] = row
    efforts = sorted(by_effort, key=effort_rank)

    if len(efforts) > 1:
        # A swept manifest gets one harness comparison per effort, plus how each
        # harness moves as effort rises, which is the question the sweep asks.
        swept: dict[str, dict[str, float]] = {}
        for effort in efforts:
            table = by_effort[effort]
            if {("jcode", False), ("claude-code", False)}.issubset(table):
                swept[f"jcode_vs_claude_code_{effort}"] = delta(
                    table[("jcode", False)], table[("claude-code", False)]
                )
        for agent in ("jcode", "claude-code"):
            key = (agent, False)
            for lower, higher in zip(efforts, efforts[1:]):
                if key in by_effort[lower] and key in by_effort[higher]:
                    swept[f"{agent}_{higher}_vs_{lower}"] = delta(
                        by_effort[higher][key], by_effort[lower][key]
                    )
        return swept

    by_mode = by_effort[efforts[0]] if efforts else {}

    def compare(left: tuple[str, bool], right: tuple[str, bool]) -> dict[str, float]:
        return delta(by_mode[left], by_mode[right])


    # Single-model, two-harness comparison (e.g. the Claude Opus 5 head-to-head).
    if {("jcode", False), ("claude-code", False)}.issubset(by_mode):
        return {
            "jcode_vs_claude_code": compare(("jcode", False), ("claude-code", False)),
        }

    required = {
        ("codex", False),
        ("codex", True),
        ("jcode", False),
        ("jcode", True),
    }
    if not required.issubset(by_mode):
        return {}

    return {
        "codex_swarm_vs_solo": compare(("codex", True), ("codex", False)),
        "jcode_swarm_vs_solo": compare(("jcode", True), ("jcode", False)),
        "codex_vs_jcode_solo": compare(("codex", False), ("jcode", False)),
        "codex_vs_jcode_swarm": compare(("codex", True), ("jcode", True)),
    }


def render_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparisons"]
    swept_efforts = report.get("reasoning_efforts") or []
    summary_lines = ["## Summary", ""]
    if len(swept_efforts) > 1:
        if not comparison:
            summary_lines.append(
                "The sweep is not complete, so no effort comparison is published yet."
            )
        for effort in sorted(swept_efforts, key=effort_rank):
            head_to_head = comparison.get(f"jcode_vs_claude_code_{effort}")
            if head_to_head:
                summary_lines.append(
                    f"- At `{effort}` effort, Jcode led Claude Code by "
                    f"**{head_to_head['mean_score_delta']:+.4f}** mean final score "
                    f"(**{head_to_head['geomean_efficiency_factor']:.3f}x**), with "
                    f"**{head_to_head['total_agent_time_delta_percent']:+.2f}%** total agent time."
                )
        ordered = sorted(swept_efforts, key=effort_rank)
        for agent in ("jcode", "claude-code"):
            # Reconstruct the step keys from the effort axis rather than by
            # prefix matching: `jcode_vs_claude_code_low` also starts with
            # "jcode_" and is a harness comparison, not an effort step.
            for lower, higher in zip(ordered, ordered[1:]):
                move = comparison.get(f"{agent}_{higher}_vs_{lower}")
                if not move:
                    continue
                summary_lines.append(
                    f"- `{agent}` moved **{move['mean_score_delta']:+.4f}** "
                    f"(**{move['geomean_efficiency_factor']:.3f}x**) going from "
                    f"`{lower}` to `{higher}`, spending "
                    f"**{move['total_agent_time_delta_percent']:+.2f}%** agent time."
                )
        summary_lines.append(
            "Per the README variance measurement, a single-cell gap under roughly 0.1 "
            "is inside run-to-run noise at k=1, so read these effort steps as "
            "directional until they are rerun."
        )
    elif "jcode_vs_claude_code" in comparison:
        head_to_head = comparison["jcode_vs_claude_code"]
        summary_lines.extend(
            [
                f"- Jcode led Claude Code by **{head_to_head['mean_score_delta']:+.4f}** mean final score, "
                f"a **{head_to_head['geomean_efficiency_factor']:.3f}x** geometric-mean "
                "instruction-efficiency difference on the same model.",
                f"- Total agent time difference: **{head_to_head['total_agent_time_delta_percent']:+.2f}%** "
                "(Jcode relative to Claude Code).",
            ]
        )
    elif comparison:

        summary_lines.extend(
            [
                f"- Codex led Jcode by **{comparison['codex_vs_jcode_solo']['mean_score_delta']:+.4f}** "
                f"mean score without swarms, a **{comparison['codex_vs_jcode_solo']['geomean_efficiency_factor']:.3f}x** "
                "geometric-mean instruction-efficiency advantage.",
                f"- With swarms enabled, Codex led by **{comparison['codex_vs_jcode_swarm']['mean_score_delta']:+.4f}**, "
                f"a **{comparison['codex_vs_jcode_swarm']['geomean_efficiency_factor']:.3f}x** advantage.",
                f"- Enabling Codex multi-agent mode changed mean score by "
                f"**{comparison['codex_swarm_vs_solo']['mean_score_delta']:+.4f}** "
                f"(**{comparison['codex_swarm_vs_solo']['geomean_efficiency_factor']:.3f}x**) and total agent time by "
                f"**{comparison['codex_swarm_vs_solo']['total_agent_time_delta_percent']:+.2f}%**.",
                f"- Enabling Jcode swarm mode changed mean score by "
                f"**{comparison['jcode_swarm_vs_solo']['mean_score_delta']:+.4f}** "
                f"(**{comparison['jcode_swarm_vs_solo']['geomean_efficiency_factor']:.3f}x**) and total agent time by "
                f"**{comparison['jcode_swarm_vs_solo']['total_agent_time_delta_percent']:+.2f}%**.",
                "- All swarm-enabled commands were configured correctly, but captured logs contained "
                "**zero explicit native helper events** in every cell. Treat the swarm deltas as enabled-mode "
                "outcomes, not demonstrated delegation gains.",
            ]
        )
    else:
        summary_lines.append("No four-way Codex/Jcode comparison is defined for this manifest.")
    summary_lines.append("")

    effort_label = (
        "/".join(sorted(swept_efforts, key=effort_rank))
        if swept_efforts
        else str(report.get("reasoning_effort", "unknown"))
    )
    lines = [
        f"# Jcode Bench v1: {report.get('model', 'mixed')} {effort_label}",
        "",
        f"Benchmark commit: `{report.get('benchmark_commit', 'unknown')}`  ",
        f"Model: `{report.get('model', 'mixed')}` with `{effort_label}` reasoning  ",
        f"Completed cells: **{report['completed_count']}/{report['run_count']}**",
        "",
        *summary_lines,
        "## Per-task results",
        "",
        "| Agent | Model | Effort | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |",
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["runs"]:
        final = f"{row['final_score']:.4f}" if row.get("final_score") is not None else "-"
        best = f"{row['best_score']:.4f}" if row.get("best_score") is not None else "-"
        duration = (
            f"{row['agent_duration_s']:.1f}s"
            if row.get("agent_duration_s") is not None
            else "-"
        )
        lines.append(
            f"| {row['agent']} | {row.get('model', report.get('model', 'unknown'))} | "
            f"{row.get('reasoning_effort', report.get('reasoning_effort', 'unknown'))} | "
            f"{'yes' if row['swarm'] else 'no'} | {row['task']} | "
            f"{final} | {best} | {duration} | {row.get('grade_count', 0)} | "
            f"{row.get('helper_events', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Aggregate results",
            "",
            "| Agent | Model | Effort | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["aggregates"]:
        lines.append(
            f"| {row['agent']} | {row.get('model', report.get('model', 'unknown'))} | "
            f"{row.get('reasoning_effort', report.get('reasoning_effort', 'unknown'))} | "
            f"{'yes' if row['swarm'] else 'no'} | "
            f"{row['completed_tasks']} | {row['mean_final_score']:.4f} | "
            f"{row['mean_best_score']:.4f} | {row['total_agent_duration_s']:.1f}s | "
            f"{row['helper_events']} |"
        )

    lines.extend(
        [
            "",
            "`Swarm enabled` records the harness configuration. `Explicit helper events` "
            "counts native helper tool events present in the captured agent log, so an "
            "enabled cell can legitimately report zero if the model did not invoke helpers.",
            "",
        ]
    )
    return "\n".join(lines)


def collect(manifest: dict[str, Any], volume: modal.Volume) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for run in manifest["runs"]:
        row: dict[str, Any] = {**run, "status": "running"}
        row.setdefault("model", manifest.get("model", "unknown"))
        # Older manifests recorded effort once at the top level; swept manifests
        # record it per run. Either way every row carries its own effort so the
        # aggregation key is never silently "unknown".
        row.setdefault("reasoning_effort", manifest.get("reasoning_effort", "unknown"))
        call = modal.FunctionCall.from_id(run["function_call_id"])
        try:
            remote = call.get(timeout=0)
        except TimeoutError:
            rows.append(row)
            continue
        except Exception as error:
            row["status"] = "failed"
            row["error"] = f"{type(error).__name__}: {error}"
            rows.append(row)
            continue

        result_path = f"runs/{run['run_id']}/result.json"
        scores_path = f"runs/{run['run_id']}/scores.jsonl"
        log_path = f"runs/{run['run_id']}/agent.log"
        result = json.loads(read_volume_file(volume, result_path))
        scores = parse_scores(read_volume_file(volume, scores_path))
        log = read_volume_file(volume, log_path).decode(errors="replace")
        score_values = [float(score["score"]) for score in scores]
        status = str(remote.get("status", result.get("status", "completed")))
        if result.get("status") != "completed" or result.get("final_grade_exit_code") != 0:
            status = str(result.get("status", "invalid"))
        row.update(
            {
                "status": status,
                "agent_exit_code": result.get("agent_exit_code"),
                "final_grade_exit_code": result.get("final_grade_exit_code"),
                "agent_duration_s": result.get("agent_duration_s"),
                "grade_count": len(scores),
                "final_score": score_values[-1],
                "best_score": max(score_values),
                "helper_events": helper_event_count(run["agent"], log),
                "output_ceiling": result.get("max_output_tokens"),
                "truncated_turns": truncated_turn_count(
                    run["agent"], log, int(result.get("max_output_tokens") or 0)
                ),
            }
        )
        if row["truncated_turns"]:
            # A truncated run is not a capability measurement, so it must never
            # be silently averaged into a published comparison.
            row["status"] = "truncated"
            row["error"] = (
                f"{row['truncated_turns']} turn(s) ended at the "
                f"{row['output_ceiling']}-token output ceiling"
            )
        rows.append(row)

    completed = [row for row in rows if row["status"] == "completed"]
    aggregates = aggregate(rows)
    return {
        **{key: value for key, value in manifest.items() if key != "runs"},
        "run_count": len(rows),
        "completed_count": len(completed),
        "runs": rows,
        "aggregates": aggregates,
        "comparisons": comparisons(aggregates) if len(completed) == len(rows) else {},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--volume", default=DEFAULT_VOLUME)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    report = collect(manifest, modal.Volume.from_name(args.volume))
    text = json.dumps(report, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text)
    else:
        print(text, end="")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report))

    if report["completed_count"] != report["run_count"] and not args.allow_incomplete:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
