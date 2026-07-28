#!/usr/bin/env python3
"""Launch the Claude Opus 5 harness comparison on the deployed Modal app.

Cells are the cross product of harness (jcode solo, Claude Code), Jcode Bench v1
task, and reasoning effort, all on one model (`claude-opus-5`, Anthropic API)
with a 20-hour agent budget each. The default `--efforts low medium high` sweep
is 18 cells. Nothing runs at import time.

    ~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py --mode pilot --task json-unescape
    ~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py --mode full --efforts low medium high
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-opus5"
TASKS = ("json-unescape", "float-print", "utf16-transcode")
HARNESSES = ("jcode", "claude-code")
EFFORTS = ("low", "medium", "high")
MODEL = "claude-opus-5"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--task", choices=TASKS, default="json-unescape", help="Pilot task")
    parser.add_argument("--tasks", nargs="+", choices=TASKS, help="Explicit task subset")
    parser.add_argument(
        "--harnesses", nargs="+", choices=HARNESSES, help="Explicit harness subset"
    )
    parser.add_argument(
        "--efforts",
        nargs="+",
        choices=EFFORTS,
        default=list(EFFORTS),
        help="Reasoning efforts to sweep; each one is an independent cell",
    )
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tasks = (args.task,) if args.mode == "pilot" else tuple(args.tasks or TASKS)
    harnesses = tuple(args.harnesses or HARNESSES)
    efforts = tuple(dict.fromkeys(args.efforts))
    worker = modal.Function.from_name(APP_NAME, "run_case")

    launches = []
    for effort in efforts:
        for task in tasks:
            for harness in harnesses:
                # The effort belongs in the run id: without it, two cells of the
                # same sweep would share a results directory and the second one
                # would resume the first one's checkpoint.
                run_id = f"{timestamp}-opus5-{effort}-{harness}-{task}"
                call = worker.spawn(harness, task, run_id, effort)
                launches.append(
                    {
                        "run_id": run_id,
                        "function_call_id": call.object_id,
                        "agent": harness,
                        "swarm": False,
                        "task": task,
                        "model": MODEL,
                        "reasoning_effort": effort,
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
        "model": MODEL,
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "reasoning_efforts": list(efforts),
        "reasoning_effort": efforts[0] if len(efforts) == 1 else "swept",
        "agent_budget_hours": 20,
        "runs": launches,
    }
    output_dir = Path(__file__).parent / "launches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timestamp}-opus5-{args.mode}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {output}")


if __name__ == "__main__":
    main()
