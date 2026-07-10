#!/usr/bin/env python3
"""Launch the pilot or full Jcode Bench v1 matrix on the deployed Modal app."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-gpt56"
TASKS = ("json-unescape", "float-print", "utf16-transcode")
CELLS = (("codex", False), ("codex", True), ("jcode", False), ("jcode", True))
CELL_NAMES = {
    "codex-solo": ("codex", False),
    "codex-swarm": ("codex", True),
    "jcode-solo": ("jcode", False),
    "jcode-swarm": ("jcode", True),
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
    cells = tuple(CELL_NAMES[name] for name in args.cells) if args.cells else CELLS
    worker = modal.Function.from_name(APP_NAME, "run_case")
    launches = []
    for task in tasks:
        for agent, swarm in cells:
            run_id = f"{timestamp}-{agent}-{'swarm' if swarm else 'solo'}-{task}"
            call = worker.spawn(agent, swarm, task, run_id)
            launches.append(
                {
                    "run_id": run_id,
                    "function_call_id": call.object_id,
                    "agent": agent,
                    "swarm": swarm,
                    "task": task,
                }
            )
            print(f"launched {run_id}: {call.object_id}")

    manifest = {
        "app": APP_NAME,
        "mode": args.mode,
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "runs": launches,
    }
    output_dir = Path(__file__).parent / "launches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timestamp}-{args.mode}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {output}")


if __name__ == "__main__":
    main()
