#!/usr/bin/env python3
"""Launch the matched three-task Codex Ultra matrix on Modal."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-codex-ultra"
BENCH_COMMIT = "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0"
CODEX_VERSION = "0.144.1"
MODEL = "gpt-5.6-sol"
TASKS = ("json-unescape", "float-print", "utf16-transcode")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=TASKS)
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    worker = modal.Function.from_name(APP_NAME, "run_case")
    launches = []
    for task in args.tasks:
        run_id = f"{timestamp}-codex-ultra-{task}"
        call = worker.spawn(task, run_id)
        launches.append(
            {
                "run_id": run_id,
                "function_call_id": call.object_id,
                "cell": "codex-ultra",
                "agent": "codex",
                "swarm": True,
                "multi_agent_enabled": True,
                "task": task,
                "model": MODEL,
                "reasoning_effort": "ultra",
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
        "mode": "full",
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "agent": "codex",
        "codex_version": CODEX_VERSION,
        "model": MODEL,
        "reasoning_effort": "ultra",
        "multi_agent_enabled": True,
        "agent_threads": 8,
        "agent_depth": 4,
        "runs": launches,
    }
    output_dir = Path(__file__).parent / "launches"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timestamp}-codex-ultra-full.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest: {output}")


if __name__ == "__main__":
    main()
