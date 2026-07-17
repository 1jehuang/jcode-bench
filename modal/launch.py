#!/usr/bin/env python3
"""Launch the pilot or full Jcode Bench v1 matrix on the deployed Modal app."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-gpt56"
BENCH_COMMIT = "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0"
TASKS = ("json-unescape", "float-print", "utf16-transcode")
MODEL = "gpt-5.6-sol"
OPUS_MODEL = "claude-opus-4-8"
DEFAULT_CELLS = ("codex-solo", "codex-swarm", "jcode-solo", "jcode-swarm")
CELL_NAMES = {
    "codex-solo": ("codex", False, MODEL),
    "codex-swarm": ("codex", True, MODEL),
    "jcode-solo": ("jcode", False, MODEL),
    "jcode-swarm": ("jcode", True, MODEL),
    "opencode-sol56": ("opencode", False, MODEL),
    "opencode-opus48": ("opencode", False, OPUS_MODEL),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--task", choices=TASKS, default="json-unescape", help="Pilot task")
    parser.add_argument("--tasks", nargs="+", choices=TASKS, help="Explicit full-run task subset")
    parser.add_argument("--cells", nargs="+", choices=tuple(CELL_NAMES), help="Explicit matrix cell subset")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tasks = (args.task,) if args.mode == "pilot" else tuple(args.tasks or TASKS)
    cell_names = tuple(args.cells or DEFAULT_CELLS)
    worker = modal.Function.from_name(APP_NAME, "run_case")
    launches = []
    for task in tasks:
        for cell_name in cell_names:
            agent, swarm, model = CELL_NAMES[cell_name]
            run_id = f"{timestamp}-{cell_name}-{task}"
            call = worker.spawn(agent, swarm, task, run_id, model)
            launches.append(
                {
                    "run_id": run_id,
                    "function_call_id": call.object_id,
                    "cell": cell_name,
                    "agent": agent,
                    "swarm": swarm,
                    "task": task,
                    "model": model,
                }
            )
            print(f"launched {run_id}: {call.object_id}")

    manifest = {
        "app": APP_NAME,
        "benchmark_commit": BENCH_COMMIT,
        "runner_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip(),
        "mode": args.mode,
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "reasoning_effort": "high",
        "opencode_version": "1.0.203",
        "runs": launches,
    }
    models = sorted({run["model"] for run in launches})
    manifest["model"] = models[0] if len(models) == 1 else "mixed"
    output_dir = Path(__file__).parent / "launches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timestamp}-{args.mode}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {output}")


if __name__ == "__main__":
    main()
