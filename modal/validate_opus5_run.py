#!/usr/bin/env python3
"""Validate an Opus 5 head-to-head manifest before its numbers may be published.

The Opus 5 pilot taught us that a benchmark cell can complete the official
grade, exit zero, and still be meaningless. This script encodes every validity
gate so a favorable-looking number cannot be published on a bad run:

1. model identity: each cell's preflight recorded the intended model;
2. no truncation: no turn ended exactly at the model's output ceiling;
3. correctness: the official final grade exited zero;
4. budget use: the cell did not exit after using a trivial slice of its budget;
5. matched conditions: every cell shares the benchmark commit, prompt, effort,
   agent budget, and pinned harness artifacts.

Exit code 0 means every completed cell is publishable. Exit code 1 means at
least one gate failed. Exit code 2 means cells are still running.

    ~/.local/share/uv/tools/modal/bin/python modal/validate_opus5_run.py \
      modal/runs/2026-07-24-opus5-head-to-head.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import modal


DEFAULT_VOLUME = "jcode-bench-v1-results"
# A cell that exits cleanly after using less than this share of its wall-clock
# budget is suspicious: the Opus 5 truncation bug produced a clean exit at 4.2%.
MIN_BUDGET_FRACTION = 0.10
# A container that starts well after the manifest was launched was preempted and
# restarted, so its wall-clock duration is not comparable to a clean cell.
RESTART_TOLERANCE_S = 15 * 60
# Fields that must be identical across every cell for the comparison to be fair.
# Fields that legitimately vary by task; compared per task, not globally.
PER_TASK_FIELDS = frozenset({"prompt"})
# The deliberately swept axis. When a manifest sweeps effort, cells are compared
# within an effort instead of globally, and every cell is separately checked
# against the effort it was actually launched with, so a silent effort fallback
# still voids the run.
SWEPT_FIELDS = frozenset({"reasoning_effort"})
MATCHED_FIELDS = (
    "bench_commit",
    "prompt",
    "reasoning_effort",
    "agent_budget_s",
    "model",
    "max_output_tokens",
    "jcode_sha256",
    "claude_code_sha256",
)


class Failure(Exception):
    pass


def read_volume_file(volume: modal.Volume, path: str) -> bytes:
    return b"".join(volume.read_file(path))


def read_json(volume: modal.Volume, path: str) -> Any:
    return json.loads(read_volume_file(volume, path))


def output_tokens_for_turn(agent: str, event: dict[str, Any]) -> int | None:
    if agent == "jcode":
        return event.get("output") if event.get("type") == "tokens" else None
    message = event.get("message")
    if isinstance(message, dict):
        usage = message.get("usage")
        if isinstance(usage, dict):
            return usage.get("output_tokens")
    return None


def count_ceiling_turns(agent: str, log: str, ceiling: int) -> int:
    if ceiling <= 0:
        return 0
    count = 0
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and output_tokens_for_turn(agent, event) == ceiling:
            count += 1
    return count


# Claude Opus 5 published API rates, USD per million tokens. Cache reads bill at
# 10% of input and Anthropic cache writes at 125%, matching the convention used
# by the existing published cost curves.
OPUS5_INPUT_USD_PER_MTOK = 5.0
OPUS5_OUTPUT_USD_PER_MTOK = 25.0
CACHE_READ_MULTIPLIER = 0.10
CACHE_WRITE_MULTIPLIER = 1.25


def token_usage(agent: str, log: str) -> dict[str, int]:
    """Sum token usage across a run's turns for either harness."""
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if agent == "jcode":
            if event.get("type") != "tokens":
                continue
            totals["input"] += event.get("input") or 0
            totals["output"] += event.get("output") or 0
            totals["cache_read"] += event.get("cache_read_input") or 0
            totals["cache_write"] += event.get("cache_creation_input") or 0
            continue
        # Claude Code reports cumulative usage on its terminal result event.
        if event.get("type") == "result" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
            totals["input"] = usage.get("input_tokens") or 0
            totals["output"] = usage.get("output_tokens") or 0
            totals["cache_read"] = usage.get("cache_read_input_tokens") or 0
            totals["cache_write"] = usage.get("cache_creation_input_tokens") or 0
    return totals


def estimated_cost_usd(totals: dict[str, int]) -> float:
    """Cost at published Opus 5 list prices, so both harnesses are billed alike."""
    per_token_in = OPUS5_INPUT_USD_PER_MTOK / 1_000_000
    per_token_out = OPUS5_OUTPUT_USD_PER_MTOK / 1_000_000
    return round(
        totals["input"] * per_token_in
        + totals["output"] * per_token_out
        + totals["cache_read"] * per_token_in * CACHE_READ_MULTIPLIER
        + totals["cache_write"] * per_token_in * CACHE_WRITE_MULTIPLIER,
        4,
    )


def artifacts_ready(volume: modal.Volume, run_id: str) -> bool:
    """True once a cell has written the artifacts every gate needs."""
    required = ("result.json", "preflight.json", "agent.log", "scores.jsonl")
    for name in required:
        try:
            read_volume_file(volume, f"runs/{run_id}/{name}")
        except Exception:
            return False
    return True


def check_cell(
    volume: modal.Volume,
    run: dict[str, Any],
    manifest_launched_at: str | None = None,
) -> dict[str, Any]:
    run_id = run["run_id"]
    agent = run["agent"]
    result = read_json(volume, f"runs/{run_id}/result.json")
    # `problems` void a run. `disclosures` are true facts that change how the
    # number must be presented (they belong in the published caveats) but do not
    # by themselves make the measurement wrong.
    problems: list[str] = []
    disclosures: list[str] = []

    if result.get("status") != "completed":
        problems.append(f"status={result.get('status')}")
    if result.get("final_grade_exit_code") != 0:
        problems.append(f"final_grade_exit_code={result.get('final_grade_exit_code')}")

    preflight = read_json(volume, f"runs/{run_id}/preflight.json")
    expected_model = result.get("model")
    if preflight.get("observed_model") != expected_model:
        problems.append(
            f"preflight model {preflight.get('observed_model')!r} != {expected_model!r}"
        )
    # In an effort sweep the effort is the independent variable, so a cell that
    # ran at some other effort measures the wrong thing entirely.
    requested_effort = run.get("reasoning_effort")
    if requested_effort is not None:
        for source, observed in (
            ("result", result.get("reasoning_effort")),
            ("preflight", preflight.get("reasoning_effort")),
        ):
            if observed != requested_effort:
                problems.append(
                    f"{source} reasoning_effort {observed!r} != requested "
                    f"{requested_effort!r}"
                )

    ceiling = int(result.get("max_output_tokens") or 0)
    if ceiling <= 0:
        problems.append(
            "run did not record max_output_tokens, so truncation cannot be ruled out; "
            "rerun on the current app version"
        )
    log = read_volume_file(volume, f"runs/{run_id}/agent.log").decode(errors="replace")
    truncated = count_ceiling_turns(agent, log, ceiling)
    if truncated:
        problems.append(f"{truncated} turn(s) ended at the {ceiling}-token ceiling")

    # A run cut off by Modal's function ceiling never reached its own stopping
    # point, so its score is a lower bound rather than a measurement.
    if result.get("agent_timed_out"):
        problems.append(
            "agent was stopped by the infrastructure ceiling rather than finishing "
            "on its own, so the score is a lower bound and not comparable"
        )

    duration = result.get("agent_duration_s") or 0
    budget = result.get("agent_budget_s") or 0
    fraction = duration / budget if budget else 0
    if budget and not result.get("agent_timed_out") and fraction < MIN_BUDGET_FRACTION:
        # Truncation is checked separately and is a hard failure. An untruncated
        # agent that stops early genuinely decided it was finished, which is a
        # real property of the harness, not an invalid run.
        target = problems if truncated else disclosures
        target.append(
            f"exited cleanly after {fraction:.1%} of its budget "
            f"({duration:.0f}s of {budget}s)"
        )

    # Modal can preempt a container and silently restart the same FunctionCall
    # from scratch. The restart is legitimate work, but the run's wall-clock
    # timing is then not comparable to a cell that ran straight through, so it
    # must be surfaced rather than averaged in silently.
    launched_at = run.get("launched_at") or manifest_launched_at
    restarted_late_by_s = None
    if launched_at:
        try:
            started = datetime.fromisoformat(str(result.get("started_at")))
            launched = datetime.fromisoformat(str(launched_at))
            restarted_late_by_s = (started - launched).total_seconds()
        except (TypeError, ValueError):
            restarted_late_by_s = None
    if restarted_late_by_s is not None and restarted_late_by_s > RESTART_TOLERANCE_S:
        disclosures.append(
            f"container started {restarted_late_by_s / 60:.0f} min after launch, "
            "which indicates a preemption restart; wall-clock timing is not comparable"
        )

    # Claude Code emits a terminal `result` event recording why it stopped.
    # A `completed` terminal_reason means the agent decided it was finished,
    # which distinguishes a legitimate early exit from a harness cutoff.
    harness_terminal_reason = None
    if agent == "claude-code":
        for line in log.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("type") == "result":
                harness_terminal_reason = event.get("terminal_reason")
    if harness_terminal_reason and harness_terminal_reason != "completed":
        disclosures.append(
            f"harness reported terminal_reason={harness_terminal_reason!r} rather than "
            "a self-determined completion"
        )

    usage_totals = token_usage(agent, log)

    resumed = result.get("resumed_from_checkpoint")
    if resumed:
        disclosures.append(
            f"resumed from checkpoint {resumed} after a preemption, so wall-clock "
            "duration understates the work performed"
        )

    scores = [
        json.loads(line)
        for line in read_volume_file(volume, f"runs/{run_id}/scores.jsonl")
        .decode()
        .splitlines()
        if line.strip()
    ]
    if not scores:
        problems.append("scores.jsonl is empty")

    return {
        "run_id": run_id,
        "agent": agent,
        "task": run["task"],
        "reasoning_effort": result.get("reasoning_effort"),
        "final_score": float(scores[-1]["score"]) if scores else None,
        "best_score": max(float(s["score"]) for s in scores) if scores else None,
        "grade_count": len(scores),
        "agent_duration_s": duration,
        "budget_fraction": round(fraction, 4),
        "truncated_turns": truncated,
        "restarted_late_by_s": restarted_late_by_s,
        "resumed_from_checkpoint": resumed,
        "harness_terminal_reason": harness_terminal_reason,
        "token_usage": usage_totals,
        "estimated_cost_usd": estimated_cost_usd(usage_totals),
        "matched": {field: result.get(field) for field in MATCHED_FIELDS},
        "problems": problems,
        "disclosures": disclosures,
    }


# Artifact pins are per harness: a jcode cell has no Claude Code sha and vice
# versa, so these are compared within a harness. A mid-run redeploy silently
# split the jcode cells across two builds differing by 59 files, which a global
# comparison could not distinguish from a legitimately absent field.
PER_HARNESS_FIELDS = frozenset({"jcode_sha256", "claude_code_sha256"})


def check_harness_pins(cells: list[dict[str, Any]]) -> list[str]:
    """Every cell of a harness must run the identical pinned artifact."""
    problems = []
    for field in sorted(PER_HARNESS_FIELDS):
        by_agent: dict[str, set[str]] = {}
        for cell in cells:
            value = cell["matched"].get(field)
            if value is None:
                continue
            by_agent.setdefault(cell.get("agent", "unknown"), set()).add(str(value))
        for agent, values in sorted(by_agent.items()):
            if len(values) > 1:
                problems.append(
                    f"{agent} cells ran different {field} values: {sorted(values)}"
                )
    return problems


def check_matched_conditions(cells: list[dict[str, Any]]) -> list[str]:
    """Every cell must agree on the experiment's controlled variables.

    Per-task fields are compared within a task rather than globally: the prompt
    legitimately names its own task, so a global comparison would always report a
    mismatch and mask real drift.
    """
    problems = []
    problems.extend(check_harness_pins(cells))
    for field in MATCHED_FIELDS:
        if field in PER_HARNESS_FIELDS or field in SWEPT_FIELDS:
            continue
        if field in PER_TASK_FIELDS:
            by_task: dict[str, set[str]] = {}
            for cell in cells:
                by_task.setdefault(cell.get("task", "unknown"), set()).add(
                    json.dumps(cell["matched"].get(field), sort_keys=True)
                )
            for task, values in sorted(by_task.items()):
                if len(values) > 1:
                    problems.append(
                        f"cells disagree on {field} within task {task}: {sorted(values)[:2]}"
                    )
            continue
        values = {json.dumps(cell["matched"].get(field), sort_keys=True) for cell in cells}
        if len(values) > 1:
            problems.append(f"cells disagree on {field}: {sorted(values)[:2]}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--volume", default=DEFAULT_VOLUME)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    volume = modal.Volume.from_name(args.volume)

    cells, pending = [], []
    for run in manifest["runs"]:
        if not artifacts_ready(volume, run["run_id"]):
            pending.append(run["run_id"])
            continue
        cells.append(check_cell(volume, run, manifest.get("launched_at")))

    report = {
        "manifest": str(args.manifest),
        "cells": cells,
        "pending": pending,
        "matched_condition_problems": check_matched_conditions(cells) if cells else [],
    }
    report["publishable"] = bool(
        cells
        and not pending
        and not report["matched_condition_problems"]
        and all(not cell["problems"] for cell in cells)
    )

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text)

    for cell in cells:
        verdict = "OK" if not cell["problems"] else "INVALID"
        print(
            f"{verdict:8} {cell['agent']:12} {cell['task']:16} "
            f"effort={cell.get('reasoning_effort')!s:7} "
            f"final={cell['final_score']} grades={cell['grade_count']} "
            f"budget={cell['budget_fraction']:.1%} truncated={cell['truncated_turns']}"
        )
        for problem in cell["problems"]:
            print(f"         - FAIL {problem}")
        for note in cell["disclosures"]:
            print(f"         - disclose: {note}")
    for problem in report["matched_condition_problems"]:
        print(f"MISMATCH {problem}")
    for run_id in pending:
        print(f"PENDING  {run_id}")

    if pending:
        return 2
    return 0 if report["publishable"] else 1


if __name__ == "__main__":
    sys.exit(main())
