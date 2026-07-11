#!/usr/bin/env python3
"""Extract Jcode todo-tool state and confidence trajectories from benchmark logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import modal


DEFAULT_VOLUME = "jcode-bench-v1-results"


def read_file(volume: modal.Volume, path: str) -> bytes:
    return b"".join(volume.read_file(path))


def parse_todo_output(output: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decoder = json.JSONDecoder()
    todos, end = decoder.raw_decode(output.lstrip())
    goals_marker = output.find("Goals:", end)
    goals: list[dict[str, Any]] = []
    if goals_marker >= 0:
        goals, _ = decoder.raw_decode(output[goals_marker + len("Goals:") :].lstrip())
    return todos, goals


def extract_calls(log: str) -> list[dict[str, Any]]:
    lines = log.splitlines()
    active: dict[str, Any] | None = None
    calls: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        if event.get("type") == "tool_start" and event.get("name") == "todo":
            active = {
                "tool_call_id": event["id"],
                "line_number": line_number,
                "normalized_position": round((line_number - 1) / max(len(lines) - 1, 1), 6),
                "input_chunks": [],
            }
            continue
        if active is None:
            continue
        if event.get("type") == "tool_input":
            active["input_chunks"].append(event.get("delta", ""))
            continue
        if (
            event.get("type") == "tool_done"
            and event.get("name") == "todo"
            and event.get("id") == active["tool_call_id"]
        ):
            request = json.loads("".join(active.pop("input_chunks")))
            returned_todos, returned_goals = parse_todo_output(event.get("output", "[]"))
            calls.append(
                {
                    "ordinal": len(calls) + 1,
                    **active,
                    "intent": request.get("intent"),
                    "requested_goals": request.get("goals") or [],
                    "requested_todos": request.get("todos") or [],
                    "returned_goals": returned_goals,
                    "returned_todos": returned_todos,
                }
            )
            active = None
    return calls


def trajectories(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for call in calls:
        for todo in call["returned_todos"]:
            todo_id = todo["id"]
            if todo_id not in by_id:
                order.append(todo_id)
                by_id[todo_id] = {
                    "id": todo_id,
                    "content": todo["content"],
                    "priority": todo["priority"],
                    "steps": [],
                }
            by_id[todo_id]["steps"].append(
                {
                    "call": call["ordinal"],
                    "normalized_position": call["normalized_position"],
                    "status": todo["status"],
                    "confidence": todo["confidence"],
                    "completion_confidence": todo.get("completion_confidence"),
                    "confidence_history": todo.get("confidence_history", []),
                }
            )
    return [by_id[todo_id] for todo_id in order]


def format_state(todo: dict[str, Any]) -> str:
    completion = todo.get("completion_confidence")
    suffix = f"/{completion}" if completion is not None else ""
    return f"`{todo['id']}` {todo['status']} {todo['confidence']}{suffix}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Jcode solo todo and confidence data",
        "",
        "Confidence is shown as `current/completion` when completion confidence exists. "
        "Normalized position is the todo call's line position within the complete NDJSON agent log.",
        "",
        "| Task | Todo calls | Todos | Hill-climbability | Final score |",
        "|---|---:|---:|---:|---:|",
    ]
    for run in report["runs"]:
        hill_values = sorted(
            {goal["hill_climbability"] for goal in run["goals"] if "hill_climbability" in goal}
        )
        lines.append(
            f"| {run['task']} | {len(run['calls'])} | {len(run['trajectories'])} | "
            f"{', '.join(map(str, hill_values)) or '-'} | {run['final_score']:.4f} |"
        )

    for run in report["runs"]:
        lines.extend(
            [
                "",
                f"## {run['task']}",
                "",
                "### Goals",
                "",
                *[
                    f"- `{goal.get('group', 'ungrouped')}` ({goal.get('hill_climbability', '-')}): "
                    f"{goal.get('objective', '')}"
                    for goal in run["goals"]
                ],
                "",
                "### Updates",
                "",
                "| Call | Log position | Intent | Returned todo state |",
                "|---:|---:|---|---|",
            ]
        )
        for call in run["calls"]:
            states = "<br>".join(format_state(todo) for todo in call["returned_todos"])
            lines.append(
                f"| {call['ordinal']} | {call['normalized_position'] * 100:.1f}% | "
                f"{call['intent']} | {states} |"
            )

        lines.extend(
            [
                "",
                "### Confidence trajectories",
                "",
                "| Todo | Confidence by update | Status by update | Final completion confidence |",
                "|---|---|---|---:|",
            ]
        )
        for trajectory in run["trajectories"]:
            confidence = " → ".join(str(step["confidence"]) for step in trajectory["steps"])
            statuses = " → ".join(step["status"] for step in trajectory["steps"])
            final_completion = trajectory["steps"][-1]["completion_confidence"]
            lines.append(
                f"| `{trajectory['id']}`: {trajectory['content']} | {confidence} | "
                f"{statuses} | {final_completion if final_completion is not None else '-'} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--volume", default=DEFAULT_VOLUME)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    volume = modal.Volume.from_name(args.volume)
    runs = []
    for run in manifest["runs"]:
        if run["agent"] != "jcode" or run["swarm"]:
            continue
        base = f"runs/{run['run_id']}"
        calls = extract_calls(read_file(volume, f"{base}/agent.log").decode(errors="replace"))
        score_rows = [
            json.loads(line)
            for line in read_file(volume, f"{base}/scores.jsonl").decode().splitlines()
            if line.strip()
        ]
        goals: list[dict[str, Any]] = []
        seen_goals: set[tuple[Any, Any]] = set()
        for call in calls:
            for goal in call["returned_goals"]:
                key = (goal.get("group"), goal.get("objective"))
                if key not in seen_goals:
                    seen_goals.add(key)
                    goals.append(goal)
        runs.append(
            {
                **run,
                "final_score": score_rows[-1]["score"],
                "todo_call_count": len(calls),
                "goals": goals,
                "calls": calls,
                "trajectories": trajectories(calls),
            }
        )

    report = {
        "benchmark_commit": manifest["benchmark_commit"],
        "model": manifest["model"],
        "reasoning_effort": manifest["reasoning_effort"],
        "runs": runs,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report))


if __name__ == "__main__":
    main()
