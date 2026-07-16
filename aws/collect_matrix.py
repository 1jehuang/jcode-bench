#!/usr/bin/env python3
"""Collect and compare a 3-task × 2-condition JcodeBench AWS run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

TASKS = ("json-unescape", "float-print", "utf16-transcode")
CONDITIONS = ("solo", "swarm")
EXPECTED_MANAGER = "claude-api:claude-fable-5"
EXPECTED_WORKER = "openai-api:gpt-5.6-sol"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    return value if isinstance(value, dict) else {}


def read_scores(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def canonical_route(session: dict[str, Any]) -> str:
    model = str(session.get("model") or "unknown")
    if ":" in model:
        prefix, bare = model.split(":", 1)
        if prefix in {"openai-api", "claude-api", "openai-oauth", "claude-oauth"}:
            return f"{prefix}:{bare}"
    provider = str(session.get("provider_key") or "")
    if model.startswith("claude-"):
        return f"claude-api:{model}" if "oauth" not in provider else f"claude-oauth:{model}"
    if model.startswith("gpt-"):
        return f"openai-api:{model}" if "oauth" not in provider else f"openai-oauth:{model}"
    return f"{provider}:{model}" if provider else model


def session_usage(session: dict[str, Any]) -> dict[str, int]:
    total = defaultdict(int)
    for message in session.get("messages", []):
        if not isinstance(message, dict):
            continue
        usage = message.get("token_usage")
        if not isinstance(usage, dict):
            continue
        for source, target in (
            ("input_tokens", "input"),
            ("output_tokens", "output"),
            ("cache_read_input_tokens", "cache_read"),
            ("cache_creation_input_tokens", "cache_write"),
        ):
            total[target] += int(usage.get(source) or 0)
    return dict(total)


def estimate_cost(route_usage: dict[str, dict[str, int]], pricing: dict[str, Any]) -> float | None:
    prices = pricing.get("usd_per_million_tokens", {}) if isinstance(pricing, dict) else {}
    total = 0.0
    priced = False
    for route, usage in route_usage.items():
        price = prices.get(route)
        if not isinstance(price, dict):
            continue
        priced = True
        cache_read = usage.get("cache_read", 0)
        cache_write = usage.get("cache_write", 0)
        input_tokens = usage.get("input", 0)
        split_accounting = route.startswith("claude-") or cache_write > 0 or cache_read > input_tokens
        fresh_input = input_tokens if split_accounting else max(0, input_tokens - cache_read)
        total += fresh_input * float(price.get("input", 0.0)) / 1_000_000
        total += usage.get("output", 0) * float(price.get("output", 0.0)) / 1_000_000
        total += cache_read * float(price.get("cache_read", price.get("input", 0.0))) / 1_000_000
        if split_accounting:
            total += cache_write * float(price.get("cache_write", price.get("input", 0.0))) / 1_000_000
    return round(total, 6) if priced else None


def artifact_checksums(root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            checksums[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return checksums


def analyze_cell(root: Path, task: str, condition: str) -> dict[str, Any]:
    cell = root / condition / task
    result = read_json(cell / "result.json") or read_json(cell / "status.json")
    metadata = read_json(cell / "metadata.json")
    scores = read_scores(cell / "scores.jsonl")

    sessions: list[dict[str, Any]] = []
    for path in sorted((cell / "sessions").glob("session_*.json")):
        try:
            value = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(value, dict):
            sessions.append(value)

    route_sessions = defaultdict(int)
    route_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    helper_routes = defaultdict(int)
    helper_efforts = defaultdict(int)
    for session in sessions:
        route = canonical_route(session)
        route_sessions[route] += 1
        for key, value in session_usage(session).items():
            route_usage[route][key] += value
        if session.get("parent_id"):
            helper_routes[route] += 1
            helper_efforts[f"{route}@{session.get('reasoning_effort') or 'unknown'}"] += 1

    helper_count = sum(helper_routes.values())
    issues: list[str] = []
    if result.get("status") != "completed":
        issues.append(f"status={result.get('status') or 'missing'}")
    if not scores:
        issues.append("scores.jsonl missing or empty")
    if not sessions:
        issues.append("session artifacts missing")
    if condition == "solo" and helper_count:
        issues.append(f"solo run created {helper_count} helper sessions")
    if condition == "swarm":
        if not helper_count:
            issues.append("swarm run has no helper sessions")
        if EXPECTED_MANAGER not in helper_routes:
            issues.append("swarm run has no Fable manager session")
        if EXPECTED_WORKER not in helper_routes:
            issues.append("swarm run has no Sol worker session")
        if f"{EXPECTED_MANAGER}@low" not in helper_efforts:
            issues.append("Fable manager did not run at low effort")
        if f"{EXPECTED_WORKER}@high" not in helper_efforts:
            issues.append("Sol worker did not run at high effort")

    pricing = metadata.get("pricing_snapshot", {})
    usage_plain = {route: dict(values) for route, values in sorted(route_usage.items())}
    baseline_score = float(scores[0]["score"]) if scores and "score" in scores[0] else None
    final_score = result.get("final_score")
    best_score = result.get("best_score")
    if final_score is None and scores:
        final_score = scores[-1].get("score")
    if best_score is None and scores:
        best_score = max(float(row["score"]) for row in scores if "score" in row)

    checksums = artifact_checksums(cell) if cell.exists() else {}
    return {
        "task": task,
        "condition": condition,
        "complete": not issues,
        "issues": issues,
        "status": result.get("status"),
        "run_id": result.get("run_id") or metadata.get("run_id"),
        "bench_commit": result.get("bench_commit") or metadata.get("bench_commit"),
        "jcode_version": result.get("jcode_version") or metadata.get("jcode_version"),
        "jcode_sha256": result.get("jcode_sha256") or metadata.get("jcode_sha256"),
        "jcode_config_sha256": result.get("jcode_config_sha256") or metadata.get("jcode_config_sha256"),
        "swarm_prompt_sha256": result.get("swarm_prompt_sha256") or metadata.get("swarm_prompt_sha256"),
        "started_at": result.get("started_at") or metadata.get("started_at"),
        "finished_at": result.get("finished_at"),
        "duration_s": result.get("agent_duration_s"),
        "grade_count": len(scores),
        "baseline_score": baseline_score,
        "final_score": final_score,
        "best_score": best_score,
        "score_gain": round(float(final_score) - baseline_score, 6)
        if final_score is not None and baseline_score is not None
        else None,
        "session_count": len(sessions),
        "helper_count": helper_count,
        "route_session_counts": dict(sorted(route_sessions.items())),
        "helper_route_counts": dict(sorted(helper_routes.items())),
        "helper_route_effort_counts": dict(sorted(helper_efforts.items())),
        "token_usage_by_route": usage_plain,
        "estimated_api_cost_usd": estimate_cost(usage_plain, pricing),
        "ecs_task_arn": result.get("ecs_task_arn") or metadata.get("ecs_task_arn"),
        "ecs_cluster": result.get("ecs_cluster") or metadata.get("ecs_cluster"),
        "artifact_count": len(checksums),
        "artifact_sha256": checksums,
    }


def percent_change(new: float | None, old: float | None) -> float | None:
    if new is None or old in {None, 0}:
        return None
    return round((new - old) / old * 100, 3)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(row["task"], row["condition"]): row for row in rows}
    pairs = []
    for task in TASKS:
        solo = by_key[(task, "solo")]
        swarm = by_key[(task, "swarm")]
        solo_score = solo.get("final_score")
        swarm_score = swarm.get("final_score")
        pairs.append(
            {
                "task": task,
                "solo_score": solo_score,
                "swarm_score": swarm_score,
                "score_delta": round(float(swarm_score) - float(solo_score), 6)
                if solo_score is not None and swarm_score is not None
                else None,
                "solo_duration_s": solo.get("duration_s"),
                "swarm_duration_s": swarm.get("duration_s"),
                "duration_change_percent": percent_change(swarm.get("duration_s"), solo.get("duration_s")),
                "solo_cost_usd": solo.get("estimated_api_cost_usd"),
                "swarm_cost_usd": swarm.get("estimated_api_cost_usd"),
                "cost_change_percent": percent_change(
                    swarm.get("estimated_api_cost_usd"), solo.get("estimated_api_cost_usd")
                ),
                "swarm_helpers": swarm.get("helper_count"),
            }
        )

    valid_scores = [pair for pair in pairs if pair["score_delta"] is not None]
    return {
        "complete_cells": sum(bool(row["complete"]) for row in rows),
        "expected_cells": len(TASKS) * len(CONDITIONS),
        "all_cells_valid": all(bool(row["complete"]) for row in rows),
        "solo_passes": sum(row.get("status") == "completed" for row in rows if row["condition"] == "solo"),
        "swarm_passes": sum(row.get("status") == "completed" for row in rows if row["condition"] == "swarm"),
        "mean_score_delta": round(sum(pair["score_delta"] for pair in valid_scores) / len(valid_scores), 6)
        if valid_scores
        else None,
        "swarm_wins": sum(pair["score_delta"] > 0 for pair in valid_scores),
        "ties": sum(pair["score_delta"] == 0 for pair in valid_scores),
        "solo_wins": sum(pair["score_delta"] < 0 for pair in valid_scores),
        "pairs": pairs,
    }


def markdown_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# JcodeBench solo vs swarm",
        "",
        f"Artifact gate: **{summary['complete_cells']}/{summary['expected_cells']} valid cells**",
        "",
        "| Task | Solo score | Swarm score | Δ score | Swarm helpers | Solo cost | Swarm cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pair in summary["pairs"]:
        lines.append(
            f"| {pair['task']} | {pair['solo_score']} | {pair['swarm_score']} | {pair['score_delta']} | "
            f"{pair['swarm_helpers']} | {pair['solo_cost_usd']} | {pair['swarm_cost_usd']} |"
        )
    lines.extend(
        [
            "",
            f"Mean score delta: **{summary['mean_score_delta']}**",
            f"Task outcomes: **{summary['swarm_wins']} swarm wins, {summary['ties']} ties, {summary['solo_wins']} solo wins**",
            "",
            "## Validation issues",
            "",
        ]
    )
    found = False
    for row in rows:
        for issue in row["issues"]:
            found = True
            lines.append(f"- `{row['condition']}/{row['task']}`: {issue}")
    if not found:
        lines.append("- None. All routes, efforts, grader outputs, sessions, and result artifacts passed validation.")
    return "\n".join(lines) + "\n"


def sync_s3(bucket: str, run_group: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        "aws",
        "s3",
        "sync",
        f"s3://{bucket}/runs/{run_group}",
        str(destination),
        "--only-show-errors",
    ]
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", nargs="?", type=Path)
    parser.add_argument("--bucket")
    parser.add_argument("--run-group")
    parser.add_argument("--output-dir", type=Path, default=Path("aws/collected"))
    args = parser.parse_args()

    if args.bucket or args.run_group:
        if not args.bucket or not args.run_group:
            parser.error("--bucket and --run-group must be supplied together")
        run_root = args.output_dir / args.run_group
        sync_s3(args.bucket, args.run_group, run_root)
    elif args.run_root:
        run_root = args.run_root
    else:
        parser.error("provide run_root or --bucket plus --run-group")

    rows = [analyze_cell(run_root, task, condition) for condition in CONDITIONS for task in TASKS]
    summary = summarize(rows)
    analysis = {"run_root": str(run_root), "rows": rows, "summary": summary}
    (run_root / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    (run_root / "analysis.md").write_text(markdown_report(rows, summary))
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["all_cells_valid"] else 2)


if __name__ == "__main__":
    main()
