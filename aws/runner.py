#!/usr/bin/env python3
"""Run one Jcode Bench v1 task durably on ECS Fargate.

The supervisor keeps one Jcode session alive until the configured wall-clock
deadline. If a headless turn exits early, it resumes the same persisted session
with another optimization prompt. Artifacts and heartbeats are synchronized to
S3 every five minutes, so the run does not depend on the launcher's connection.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASKS = ("json-unescape", "float-print", "utf16-transcode")
BENCH_COMMIT = "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0"
CHECKPOINT_SECONDS = 300
GRADE_ATTEMPTS = 5

TASK = os.environ["TASK"]
RUN_GROUP = os.environ["RUN_GROUP"]
S3_BUCKET = os.environ["S3_BUCKET"]
SECRET_ID = os.environ["SECRET_ID"]
MODEL = os.environ.get("MODEL", "gpt-5.6-sol")
REASONING_EFFORT = os.environ.get("REASONING_EFFORT", "high")
BUDGET_SECONDS = int(os.environ.get("BUDGET_SECONDS", "43200"))
JCODE_VERSION = os.environ["JCODE_VERSION"]
JCODE_SHA256 = os.environ["JCODE_SHA256"]

if TASK not in TASKS:
    raise SystemExit(f"unsupported task: {TASK}")

RUN_ID = f"{RUN_GROUP}-jcode-solo-{TASK}"
S3_URI = f"s3://{S3_BUCKET}/runs/{RUN_GROUP}/{TASK}"
WORK_ROOT = Path("/work/run")
WORKDIR = WORK_ROOT / "tasks" / TASK
HOME = WORK_ROOT / "home"
RESULT_DIR = Path("/work/result")
STOP = threading.Event()
CURRENT_PROCESS: subprocess.Popen[str] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def fetch_openai_key() -> str:
    response = run(
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            SECRET_ID,
            "--query",
            "SecretString",
            "--output",
            "text",
        ]
    )
    if response.returncode != 0 or not response.stdout.strip():
        raise RuntimeError(f"could not read OpenAI secret: {response.stdout[-1000:]}")
    return response.stdout.strip()


def parse_scores() -> list[dict[str, Any]]:
    path = WORKDIR / "scores.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def snapshot(label: str) -> None:
    destination = RESULT_DIR / "checkpoints" / label
    destination.mkdir(parents=True, exist_ok=True)
    submission = WORKDIR / "submission"
    if submission.exists():
        shutil.copytree(submission, destination / "submission", dirs_exist_ok=True)
    scores = WORKDIR / "scores.jsonl"
    if scores.exists():
        shutil.copy2(scores, destination / "scores.jsonl")
        shutil.copy2(scores, RESULT_DIR / "scores.jsonl")
    sessions = HOME / ".jcode" / "sessions"
    if sessions.exists():
        shutil.copytree(sessions, RESULT_DIR / "sessions", dirs_exist_ok=True)


def upload() -> None:
    response = run(["aws", "s3", "sync", str(RESULT_DIR), S3_URI, "--only-show-errors"])
    if response.returncode != 0:
        print(f"checkpoint upload failed: {response.stdout[-1000:]}", flush=True)


def heartbeat(started_monotonic: float, deadline: float, segment: int) -> None:
    scores = parse_scores()
    write_json(
        RESULT_DIR / "status.json",
        {
            "run_id": RUN_ID,
            "status": "running",
            "task": TASK,
            "updated_at": utc_now(),
            "elapsed_s": round(time.monotonic() - started_monotonic, 3),
            "remaining_s": max(0, round(deadline - time.monotonic(), 3)),
            "segment": segment,
            "grade_count": len(scores),
            "best_score": max((float(row["score"]) for row in scores), default=None),
        },
    )


def checkpoint_loop(started_monotonic: float, deadline: float, segment_ref: list[int]) -> None:
    while not STOP.wait(CHECKPOINT_SECONDS):
        label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot(label)
        heartbeat(started_monotonic, deadline, segment_ref[0])
        upload()
        print(f"checkpoint {label} uploaded to {S3_URI}", flush=True)


def run_grade(log_name: str, *, full: bool = False) -> int:
    log_path = RESULT_DIR / log_name
    with log_path.open("w", buffering=1) as log:
        for attempt in range(1, GRADE_ATTEMPTS + 1):
            log.write(f"=== grade attempt {attempt}/{GRADE_ATTEMPTS} ===\n")
            command = ["./grade"] + (["--full"] if full else [])
            grade = subprocess.run(command, cwd=WORKDIR, stdout=log, stderr=subprocess.STDOUT, text=True, check=False)
            if grade.returncode == 0:
                return 0
            log.write(f"grade attempt {attempt} exited {grade.returncode}\n")
            shutil.rmtree(WORKDIR / ".build", ignore_errors=True)
            time.sleep(min(attempt, 3))
    return grade.returncode


def newest_session_id() -> str | None:
    sessions = HOME / ".jcode" / "sessions"
    candidates = list(sessions.glob("session_*.json")) if sessions.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime).stem


def initial_prompt() -> str:
    return f"""You are being benchmarked on jcode bench task {TASK}, in this directory.

Read spec.md. Your job: make submission/solve.c faster. Correctness on every input is a hard gate, verified by ./grade. Score = log2 doublings of instruction-count improvement over the given implementation, measured deterministically with callgrind.

The loop: edit submission/solve.c (you may add more .c/.h files in submission/), run ./grade, read your score. Grade often; every grade is logged to scores.jsonl as your score-over-time curve.

Rules: edit only files under submission/. Self-contained C17, libc only. Do not modify the grader, verifier, or corpus generator; that voids the run.

You have a 12-hour wall-clock budget. Use it. Do not stop after the first strong solution or merely because progress slows. Keep a concrete optimization todo list, investigate multiple algorithmic and low-level approaches, validate each promising change, revert regressions, and continue until the supervisor ends the run. Aim as high as you can; +1.0 means 2x, +2.0 means 4x."""


def continuation_prompt(segment: int, remaining_s: float) -> str:
    return f"""Continue the same benchmark optimization run. Segment {segment} has started and about {remaining_s / 3600:.2f} hours remain in the fixed budget.

Do not just summarize or declare the current result sufficient. Re-read the current submission and scores.jsonl, identify a genuinely different optimization angle or a weakness in the present approach, update your todo list, implement and grade experiments, preserve only verified improvements, and keep working until this turn is ended by the supervisor."""


def run_jcode_segment(env: dict[str, str], prompt: str, session_id: str | None, remaining_s: float, segment: int) -> int:
    global CURRENT_PROCESS
    command = [
        "jcode",
        "--no-update",
        "--no-selfdev",
        "-p",
        "openai-api",
        "-m",
        MODEL,
        "-C",
        str(WORKDIR),
        "run",
        "--ndjson",
        "--trace",
        "--quiet",
    ]
    if session_id:
        command.extend(["--resume", session_id])
    command.append(prompt)

    with (RESULT_DIR / "agent.log").open("a", buffering=1) as log:
        log.write(f"\n=== segment {segment} started {utc_now()} session={session_id or 'new'} ===\n")
        CURRENT_PROCESS = subprocess.Popen(
            command,
            cwd=WORKDIR,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            return CURRENT_PROCESS.wait(timeout=max(1, remaining_s))
        except subprocess.TimeoutExpired:
            log.write(f"\n=== fixed budget reached; terminating segment {segment} ===\n")
            CURRENT_PROCESS.send_signal(signal.SIGINT)
            try:
                return CURRENT_PROCESS.wait(timeout=60)
            except subprocess.TimeoutExpired:
                CURRENT_PROCESS.kill()
                return CURRENT_PROCESS.wait(timeout=30)
        finally:
            CURRENT_PROCESS = None


def handle_signal(signum: int, _frame: object) -> None:
    STOP.set()
    if CURRENT_PROCESS is not None and CURRENT_PROCESS.poll() is None:
        CURRENT_PROCESS.terminate()
    snapshot("termination")
    upload()
    raise SystemExit(128 + signum)


def main() -> None:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    shutil.rmtree(WORK_ROOT, ignore_errors=True)
    shutil.rmtree(RESULT_DIR, ignore_errors=True)
    WORKDIR.parent.mkdir(parents=True, exist_ok=True)
    HOME.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("/opt/jcode-bench/harness"), WORK_ROOT / "harness")
    shutil.copytree(Path("/opt/jcode-bench/tasks") / TASK, WORKDIR, ignore=shutil.ignore_patterns(".build", "scores.jsonl"))

    started_at = utc_now()
    started_monotonic = time.monotonic()
    deadline = started_monotonic + BUDGET_SECONDS
    metadata = {
        "run_id": RUN_ID,
        "status": "starting",
        "agent": "jcode",
        "swarm": False,
        "task": TASK,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "budget_seconds": BUDGET_SECONDS,
        "bench_commit": BENCH_COMMIT,
        "jcode_version": JCODE_VERSION,
        "jcode_sha256": JCODE_SHA256,
        "started_at": started_at,
        "s3_uri": S3_URI,
        "prompt": initial_prompt(),
    }
    write_json(RESULT_DIR / "metadata.json", metadata)
    upload()

    baseline_exit = run_grade("baseline-grade.log")
    if baseline_exit != 0:
        write_json(RESULT_DIR / "result.json", {**metadata, "status": "baseline_failed", "exit_code": baseline_exit, "finished_at": utc_now()})
        upload()
        raise SystemExit(baseline_exit)

    snapshot("baseline")
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(HOME),
            "CI": "1",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "OPENAI_API_KEY": fetch_openai_key(),
            "JCODE_PROVIDER": "openai-api",
            "JCODE_MODEL": MODEL,
            "JCODE_OPENAI_REASONING_EFFORT": REASONING_EFFORT,
            "JCODE_SWARM_ENABLED": "false",
            "JCODE_MEMORY_ENABLED": "false",
            "JCODE_AUTO_UPDATE": "false",
        }
    )

    segment_ref = [0]
    checkpointer = threading.Thread(
        target=checkpoint_loop,
        args=(started_monotonic, deadline, segment_ref),
        daemon=True,
    )
    checkpointer.start()

    segment_results = []
    try:
        session_id = None
        while time.monotonic() < deadline and not STOP.is_set():
            segment_ref[0] += 1
            remaining_s = deadline - time.monotonic()
            prompt = initial_prompt() if segment_ref[0] == 1 else continuation_prompt(segment_ref[0], remaining_s)
            exit_code = run_jcode_segment(env, prompt, session_id, remaining_s, segment_ref[0])
            session_id = newest_session_id() or session_id
            segment_results.append(
                {
                    "segment": segment_ref[0],
                    "finished_at": utc_now(),
                    "exit_code": exit_code,
                    "session_id": session_id,
                    "remaining_s": max(0, round(deadline - time.monotonic(), 3)),
                }
            )
            write_json(RESULT_DIR / "segments.json", segment_results)
            snapshot(f"segment-{segment_ref[0]:03d}")
            heartbeat(started_monotonic, deadline, segment_ref[0])
            upload()
            if time.monotonic() < deadline:
                time.sleep(5)
    finally:
        STOP.set()
        checkpointer.join(timeout=15)

    snapshot("agent-final")
    final_grade_exit = run_grade("final-grade.log", full=TASK == "float-print")
    snapshot("final-grade")
    scores = parse_scores()
    result = {
        **metadata,
        "status": "completed" if final_grade_exit == 0 else "final_grade_failed",
        "final_grade_exit_code": final_grade_exit,
        "finished_at": utc_now(),
        "agent_duration_s": round(time.monotonic() - started_monotonic, 3),
        "segments": segment_results,
        "grade_count": len(scores),
        "best_score": max((float(row["score"]) for row in scores), default=None),
        "final_score": float(scores[-1]["score"]) if scores else None,
    }
    write_json(RESULT_DIR / "result.json", result)
    write_json(RESULT_DIR / "status.json", {**result, "updated_at": utc_now()})
    upload()
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if final_grade_exit == 0 else 1)


if __name__ == "__main__":
    main()
