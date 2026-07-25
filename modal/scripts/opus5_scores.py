#!/usr/bin/env python3
"""Summarize official grader scores from a benchmark cell's agent log.

Scores are read from the log rather than from a volume checkpoint: checkpoints
only snapshot when the submission tree changes, so a cell that graded several
times without editing files kept reporting a stale baseline score.

Both harness log shapes are handled: jcode reports tool results on `tool_done`
events, Claude Code as user-role `tool_result` messages.
"""

from __future__ import annotations

import json
import re
import sys

# The decimal point is required. Agents sometimes echo the grader's own source,
# which contains a literal `SCORE   {score:+.4f}` template that a looser pattern
# matched as a real score of 0.0000.
SCORE = re.compile(r"SCORE\s+([+-][0-9]+\.[0-9]+)")


def main() -> None:
    best: float | None = None
    count = 0
    for line in sys.stdin:
        line = line.strip()
        if not line.startswith("{") or "SCORE" not in line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") not in ("tool_done", "user"):
            continue
        for match in SCORE.finditer(json.dumps(event).replace("\\n", "\n")):
            value = float(match.group(1))
            count += 1
            if best is None or value > best:
                best = value
    print(f"{count} grades best={best:+.4f}" if best is not None else "no grades yet")


if __name__ == "__main__":
    main()
