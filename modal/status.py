#!/usr/bin/env python3
"""Show status for a launch manifest without blocking for completion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import modal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    for run in manifest["runs"]:
        call = modal.FunctionCall.from_id(run["function_call_id"])
        try:
            result = call.get(timeout=0)
        except TimeoutError:
            status = "running"
        except Exception as error:  # Modal reports remote terminal errors here.
            status = f"failed: {type(error).__name__}: {error}"
        else:
            status = str(result.get("status", "completed"))
        print(f"{run['run_id']}: {status}")


if __name__ == "__main__":
    main()
