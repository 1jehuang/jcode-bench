#!/usr/bin/env python3
"""Launch the multi-model Jcode Bench v1 matrix on the deployed Modal app.

By default this launches 12 runs: 4 models x 3 tasks, jcode solo, 20-hour
agent budget each. Nothing runs at import time; runs launch only when this
script is executed.

    ~/.local/share/uv/tools/modal/bin/python modal/multimodel_launch.py --mode pilot --task json-unescape
    ~/.local/share/uv/tools/modal/bin/python modal/multimodel_launch.py --mode full
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-multimodel"
TASKS = ("json-unescape", "float-print", "utf16-transcode")
MODELS = (
    "gpt-5.4",
    "gpt-5.5",
    "gpt-5.6-sol",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-opus-4-8",
)


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
        "agent_budget_hours": 20,
        "runs": launches,
    }
    output_dir = Path(__file__).parent / "launches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timestamp}-multimodel-{args.mode}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {output}")


if __name__ == "__main__":
    main()
