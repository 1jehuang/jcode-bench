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
from pathlib import Path
from typing import Any

import modal


DEFAULT_VOLUME = "jcode-bench-v1-results"
# A cell that exits cleanly after using less than this share of its wall-clock
# budget is suspicious: the Opus 5 truncation bug produced a clean exit at 4.2%.
MIN_BUDGET_FRACTION = 0.10
# Fields that must be identical across every cell for the comparison to be fair.
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


def artifacts_ready(volume: modal.Volume, run_id: str) -> bool:
    """True once a cell has written the artifacts every gate needs."""
    required = ("result.json", "preflight.json", "agent.log", "scores.jsonl")
    for name in required:
        try:
            read_volume_file(volume, f"runs/{run_id}/{name}")
        except Exception:
            return False
    return True


def check_cell(volume: modal.Volume, run: dict[str, Any]) -> dict[str, Any]:
    run_id = run["run_id"]
    agent = run["agent"]
    result = read_json(volume, f"runs/{run_id}/result.json")
    problems: list[str] = []

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

    ceiling = int(result.get("max_output_tokens") or 0)
    if ceiling <= 0:
        problems.append("run did not record max_output_tokens, cannot check truncation")
    log = read_volume_file(volume, f"runs/{run_id}/agent.log").decode(errors="replace")
    truncated = count_ceiling_turns(agent, log, ceiling)
    if truncated:
        problems.append(f"{truncated} turn(s) ended at the {ceiling}-token ceiling")

    duration = result.get("agent_duration_s") or 0
    budget = result.get("agent_budget_s") or 0
    fraction = duration / budget if budget else 0
    if budget and not result.get("agent_timed_out") and fraction < MIN_BUDGET_FRACTION:
        problems.append(
            f"exited cleanly after {fraction:.1%} of its budget "
            f"({duration:.0f}s of {budget}s)"
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
        "final_score": float(scores[-1]["score"]) if scores else None,
        "best_score": max(float(s["score"]) for s in scores) if scores else None,
        "grade_count": len(scores),
        "agent_duration_s": duration,
        "budget_fraction": round(fraction, 4),
        "truncated_turns": truncated,
        "matched": {field: result.get(field) for field in MATCHED_FIELDS},
        "problems": problems,
    }


def check_matched_conditions(cells: list[dict[str, Any]]) -> list[str]:
    """Every cell must agree on the experiment's controlled variables."""
    problems = []
    for field in MATCHED_FIELDS:
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
        cells.append(check_cell(volume, run))

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
            f"final={cell['final_score']} grades={cell['grade_count']} "
            f"budget={cell['budget_fraction']:.1%} truncated={cell['truncated_turns']}"
        )
        for problem in cell["problems"]:
            print(f"         - {problem}")
    for problem in report["matched_condition_problems"]:
        print(f"MISMATCH {problem}")
    for run_id in pending:
        print(f"PENDING  {run_id}")

    if pending:
        return 2
    return 0 if report["publishable"] else 1


if __name__ == "__main__":
    sys.exit(main())
