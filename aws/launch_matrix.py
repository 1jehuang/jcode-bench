#!/usr/bin/env python3
"""Launch the six-cell JcodeBench matrix using the AWS CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASKS = ("json-unescape", "float-print", "utf16-transcode")
CONDITIONS = ("solo", "swarm")


def aws_json(arguments: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        ["aws", *arguments, "--output", "json"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected AWS response for {' '.join(arguments)}")
    return value


def stop_launched(cluster: str, task_arns: list[str]) -> None:
    for task_arn in task_arns:
        subprocess.run(
            [
                "aws",
                "ecs",
                "stop-task",
                "--cluster",
                cluster,
                "--task",
                task_arn,
                "--reason",
                "matrix launch rolled back after a later cell failed",
                "--output",
                "json",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--task-definition", required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--subnet", action="append", required=True)
    parser.add_argument("--security-group", action="append", required=True)
    parser.add_argument("--assign-public-ip", choices=("ENABLED", "DISABLED"), default="ENABLED")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--secret-id", required=True)
    parser.add_argument("--run-group", required=True)
    parser.add_argument("--jcode-version", required=True)
    parser.add_argument("--jcode-sha256", required=True)
    parser.add_argument("--budget-seconds", type=int, default=3600)
    parser.add_argument("--swarm-concurrency", type=int, default=32)
    parser.add_argument("--manifest-dir", type=Path, default=Path("aws/runs"))
    args = parser.parse_args()

    if args.budget_seconds <= 0:
        parser.error("--budget-seconds must be positive")
    if args.swarm_concurrency <= 0:
        parser.error("--swarm-concurrency must be positive")

    network = json.dumps(
        {
            "awsvpcConfiguration": {
                "subnets": args.subnet,
                "securityGroups": args.security_group,
                "assignPublicIp": args.assign_public_ip,
            }
        },
        separators=(",", ":"),
    )
    launched: list[dict[str, Any]] = []
    task_arns: list[str] = []
    try:
        for condition in CONDITIONS:
            for task in TASKS:
                environment = [
                    {"name": "TASK", "value": task},
                    {"name": "CONDITION", "value": condition},
                    {"name": "RUN_GROUP", "value": args.run_group},
                    {"name": "S3_BUCKET", "value": args.bucket},
                    {"name": "SECRET_ID", "value": args.secret_id},
                    {"name": "MODEL", "value": "gpt-5.6-sol"},
                    {"name": "REASONING_EFFORT", "value": "high"},
                    {"name": "BUDGET_SECONDS", "value": str(args.budget_seconds)},
                    {"name": "SWARM_CONCURRENCY", "value": str(args.swarm_concurrency)},
                    {"name": "JCODE_VERSION", "value": args.jcode_version},
                    {"name": "JCODE_SHA256", "value": args.jcode_sha256},
                ]
                overrides = json.dumps(
                    {"containerOverrides": [{"name": args.container_name, "environment": environment}]},
                    separators=(",", ":"),
                )
                response = aws_json(
                    [
                        "ecs",
                        "run-task",
                        "--cluster",
                        args.cluster,
                        "--task-definition",
                        args.task_definition,
                        "--launch-type",
                        "FARGATE",
                        "--platform-version",
                        "LATEST",
                        "--count",
                        "1",
                        "--started-by",
                        args.run_group[:36],
                        "--network-configuration",
                        network,
                        "--overrides",
                        overrides,
                        "--tags",
                        f"key=RunGroup,value={args.run_group}",
                        f"key=Condition,value={condition}",
                        f"key=Task,value={task}",
                    ]
                )
                failures = response.get("failures") or []
                tasks = response.get("tasks") or []
                if failures or len(tasks) != 1:
                    raise RuntimeError(f"failed to launch {condition}/{task}: {failures or response}")
                task_record = tasks[0]
                task_arn = str(task_record["taskArn"])
                task_arns.append(task_arn)
                launched.append(
                    {
                        "task": task,
                        "condition": condition,
                        "task_arn": task_arn,
                        "cluster_arn": task_record.get("clusterArn"),
                        "task_definition_arn": task_record.get("taskDefinitionArn"),
                        "created_at": task_record.get("createdAt"),
                        "last_status": task_record.get("lastStatus"),
                    }
                )
                print(f"launched {condition}/{task}: {task_arn}", flush=True)
    except Exception:
        stop_launched(args.cluster, task_arns)
        raise

    manifest = {
        "run_group": args.run_group,
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "cluster": args.cluster,
        "task_definition": args.task_definition,
        "container_name": args.container_name,
        "network": json.loads(network),
        "bucket": args.bucket,
        "secret_id": args.secret_id,
        "budget_seconds": args.budget_seconds,
        "swarm_concurrency": args.swarm_concurrency,
        "jcode_version": args.jcode_version,
        "jcode_sha256": args.jcode_sha256,
        "cells": launched,
    }
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest_dir / f"{args.run_group}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            str(manifest_path),
            f"s3://{args.bucket}/runs/{args.run_group}/launch-manifest.json",
            "--only-show-errors",
        ],
        check=True,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
