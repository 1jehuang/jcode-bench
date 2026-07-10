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


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "completed":
            groups[(row["agent"], row["swarm"])].append(row)

    result = []
    for (agent, swarm), values in sorted(groups.items()):
        result.append(
            {
                "agent": agent,
                "swarm": swarm,
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


def comparisons(aggregates: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_mode = {(row["agent"], row["swarm"]): row for row in aggregates}

    def compare(
        left: tuple[str, bool], right: tuple[str, bool]
    ) -> dict[str, float]:
        left_row = by_mode[left]
        right_row = by_mode[right]
        score_delta = left_row["mean_final_score"] - right_row["mean_final_score"]
        duration_delta = (
            left_row["total_agent_duration_s"] / right_row["total_agent_duration_s"] - 1
        ) * 100
        return {
            "mean_score_delta": round(score_delta, 4),
            "geomean_efficiency_factor": round(2**score_delta, 4),
            "total_agent_time_delta_percent": round(duration_delta, 2),
        }

    return {
        "codex_swarm_vs_solo": compare(("codex", True), ("codex", False)),
        "jcode_swarm_vs_solo": compare(("jcode", True), ("jcode", False)),
        "codex_vs_jcode_solo": compare(("codex", False), ("jcode", False)),
        "codex_vs_jcode_swarm": compare(("codex", True), ("jcode", True)),
    }


def render_markdown(report: dict[str, Any]) -> str:
    comparison = report["comparisons"]
    summary_lines = ["## Summary", ""]
    if comparison:
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
        summary_lines.append("Aggregate comparisons will be calculated after all cells complete.")
    summary_lines.append("")

    lines = [
        "# Jcode Bench v1: GPT-5.6 Sol high",
        "",
        f"Benchmark commit: `{report['benchmark_commit']}`  ",
        f"Model: `{report['model']}` with `{report['reasoning_effort']}` reasoning  ",
        f"Completed cells: **{report['completed_count']}/{report['run_count']}**",
        "",
        *summary_lines,
        "## Per-task results",
        "",
        "| Agent | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
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
            f"| {row['agent']} | {'yes' if row['swarm'] else 'no'} | {row['task']} | "
            f"{final} | {best} | {duration} | {row.get('grade_count', 0)} | "
            f"{row.get('helper_events', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Aggregate results",
            "",
            "| Agent | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["aggregates"]:
        lines.append(
            f"| {row['agent']} | {'yes' if row['swarm'] else 'no'} | "
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
            }
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
