#!/usr/bin/env python3
"""Launch the isolated current-Jcode GPT-5.6 Sol Jcode Bench rerun.

Pilot mode launches one task. Full mode launches the requested subset or all
three canonical tasks, always as Jcode solo with a 20-hour agent budget.
Nothing runs at import time.

    ~/.local/share/uv/tools/modal/bin/python modal/current_sol_rerun_launch.py \
      --mode pilot --task json-unescape
    ~/.local/share/uv/tools/modal/bin/python modal/current_sol_rerun_launch.py \
      --mode full --tasks float-print utf16-transcode
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-jcode-sol-414da9a4a"
TASKS = ("json-unescape", "float-print", "utf16-transcode")
MODELS = ("gpt-5.6-sol",)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--task", choices=TASKS, default="json-unescape", help="Pilot task")
    parser.add_argument("--tasks", nargs="+", choices=TASKS, help="Explicit full-run task subset")
    parser.add_argument("--models", nargs="+", choices=MODELS, help="Explicit model subset")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tasks = (args.task,) if args.mode == "pilot" else tuple(args.tasks or TASKS)
    models = tuple(args.models or MODELS)
    worker = modal.Function.from_name(APP_NAME, "run_case")
    launches = []
    for task in tasks:
        for model in models:
            run_id = f"{timestamp}-jcode-solo-{model}-{task}"
            call = worker.spawn(model, task, run_id)
            launches.append(
                {
                    "run_id": run_id,
                    "function_call_id": call.object_id,
                    "agent": "jcode",
                    "swarm": False,
                    "task": task,
                    "model": model,
                }
            )
            print(f"launched {run_id}: {call.object_id}")

    manifest = {
        "app": APP_NAME,
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
        "benchmark_commit": "cb8ccbc29ad4f4ce4a3ada2e79e019d06729df7c",
        "tasks_tree": "8eeb5e30f8987cc909f6b7324cb6a58263ff127c",
        "harness_tree": "84568c2763dc42024400f61ad11be1baec2ec9cd",
        "jcode_version": "v0.53.34-dev (414da9a4a)",
        "jcode_source_commit": "414da9a4a67d093d60f7b0b50165135645ea42ff",
        "jcode_sha256": "825c60f739650f66b3c8fd6c674bb2c830bab57c1f54c5c40c92943c90954fc5",
        "agent_budget_hours": 20,
        "runs": launches,
    }
    output_dir = Path(__file__).parent / "launches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timestamp}-current-sol-rerun-{args.mode}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {output}")


if __name__ == "__main__":
    main()
