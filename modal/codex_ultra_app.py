"""Matched Modal runner for Codex CLI Ultra on Jcode Bench v1.

This runner is deliberately separate from the historical four-way harness image.
It pins Codex 0.144.1, GPT-5.6 Sol, Ultra reasoning, and multi-agent enablement
without mounting a Jcode binary or inheriting a user Codex configuration.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import modal


APP_NAME = "jcode-bench-v1-codex-ultra"
BENCH_COMMIT = "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0"
CODEX_VERSION = "0.144.1"
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "ultra"
MULTI_AGENT_ENABLED = True
AGENT_THREADS = 8
AGENT_DEPTH = 4
CHECKPOINT_SECONDS = 300
GRADE_ATTEMPTS = 5
TASKS = ("json-unescape", "float-print", "utf16-transcode")

ROOT = Path(__file__).resolve().parents[1]

app = modal.App(APP_NAME)
results = modal.Volume.from_name("jcode-bench-v1-results", create_if_missing=True)
openai_secret = modal.Secret.from_local_environ(["OPENAI_API_KEY"])

image = (
    modal.Image.from_registry("archlinux:base")
    .run_commands(
        "pacman -Syu --noconfirm --needed base-devel valgrind git nodejs npm jq python",
        f"npm install -g @openai/codex@{CODEX_VERSION}",
    )
    .add_local_dir(
        ROOT,
        "/opt/jcode-bench",
        copy=True,
        ignore=[".git", "**/.build", "**/scores.jsonl", "modal/launches"],
    )
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def copy_checkpoint(workdir: Path, result_dir: Path, label: str) -> None:
    destination = result_dir / "checkpoints" / label
    destination.mkdir(parents=True, exist_ok=True)
    submission = workdir / "submission"
    if submission.exists():
        shutil.copytree(submission, destination / "submission", dirs_exist_ok=True)
    scores = workdir / "scores.jsonl"
    if scores.exists():
        shutil.copy2(scores, destination / "scores.jsonl")
    results.commit()


def checkpoint_loop(stop: threading.Event, workdir: Path, result_dir: Path) -> None:
    while not stop.wait(CHECKPOINT_SECONDS):
        label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        copy_checkpoint(workdir, result_dir, label)


def prompt_for(task: str) -> str:
    return f"""You are being benchmarked on jcode bench task {task}, in this directory.

Read spec.md. Your job: make submission/solve.c faster. Correctness on every input is a hard gate, verified by ./grade. Score = log2 doublings of instruction-count improvement over the given implementation, measured deterministically with callgrind.

The loop: edit submission/solve.c (you may add more .c/.h files in submission/), run ./grade, read your score. Grade often; every grade is logged to scores.jsonl as your score-over-time curve.

Rules: edit only files under submission/. Self-contained C17, libc only. Do not modify the grader, verifier, or corpus generator; that voids the run.

Work until you genuinely cannot improve further. Aim as high as you can; +1.0 means 2x, +2.0 means 4x. Report your final score."""


def codex_command(workdir: Path, prompt: str, home: Path) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "CODEX_HOME": str(home / ".codex"),
            "CI": "1",
            "TERM": "dumb",
            "NO_COLOR": "1",
        }
    )
    Path(env["CODEX_HOME"]).mkdir(parents=True, exist_ok=True)
    login = subprocess.run(
        ["codex", "login", "--with-api-key"],
        input=env["OPENAI_API_KEY"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=60,
        check=False,
    )
    if login.returncode != 0:
        raise RuntimeError(f"Codex API login failed with exit {login.returncode}")

    return (
        [
            "codex",
            "exec",
            "--json",
            "--strict-config",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            str(workdir),
            "-m",
            MODEL,
            "-c",
            f'model_reasoning_effort="{REASONING_EFFORT}"',
            "-c",
            f"agents.max_threads={AGENT_THREADS}",
            "-c",
            f"agents.max_depth={AGENT_DEPTH}",
            "--enable",
            "multi_agent",
            prompt,
        ],
        env,
    )


def run_logged(command: list[str], env: dict[str, str], cwd: Path, log_path: Path) -> int:
    with log_path.open("w", buffering=1) as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return process.wait()


def run_grade_with_retries(workdir: Path, log_path: Path) -> int:
    last_returncode = 1
    with log_path.open("w", buffering=1) as log:
        for attempt in range(1, GRADE_ATTEMPTS + 1):
            log.write(f"=== grade attempt {attempt}/{GRADE_ATTEMPTS} ===\n")
            grade = subprocess.run(
                ["./grade"],
                cwd=workdir,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            last_returncode = grade.returncode
            if grade.returncode == 0:
                return 0
            log.write(f"grade attempt {attempt} exited {grade.returncode}\n")
            shutil.rmtree(workdir / ".build", ignore_errors=True)
            time.sleep(min(attempt, 3))
    return last_returncode


@app.function(
    image=image,
    secrets=[openai_secret],
    volumes={"/results": results},
    timeout=86_400,
    cpu=4,
    memory=8192,
    max_containers=3,
    single_use_containers=True,
    region="us-west",
    retries=modal.Retries(max_retries=3, initial_delay=5.0, backoff_coefficient=2.0),
)
def run_case(task: str, run_id: str) -> dict[str, object]:
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")

    result_dir = Path("/results/runs") / run_id
    result_path = result_dir / "result.json"
    if result_path.exists():
        prior = json.loads(result_path.read_text())
        if prior.get("status") == "completed":
            return prior

    source = Path("/opt/jcode-bench/tasks") / task
    work_root = Path("/tmp/jcode-bench") / run_id
    workdir = work_root / "tasks" / task
    home = work_root / "home"
    shutil.rmtree(work_root, ignore_errors=True)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path("/opt/jcode-bench/harness"), work_root / "harness")
    shutil.copytree(source, workdir, ignore=shutil.ignore_patterns(".build", "scores.jsonl"))

    result_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    metadata = {
        "run_id": run_id,
        "status": "running",
        "agent": "codex",
        "swarm": True,
        "multi_agent_enabled": MULTI_AGENT_ENABLED,
        "task": task,
        "model": MODEL,
        "provider": "openai",
        "reasoning_effort": REASONING_EFFORT,
        "agent_threads": AGENT_THREADS,
        "agent_depth": AGENT_DEPTH,
        "bench_commit": BENCH_COMMIT,
        "codex_version": CODEX_VERSION,
        "started_at": started_at,
        "prompt": prompt_for(task),
    }
    write_json(result_dir / "metadata.json", metadata)
    results.commit()

    baseline_log = result_dir / "baseline-grade.log"
    baseline_exit_code = run_grade_with_retries(workdir, baseline_log)
    if baseline_exit_code != 0:
        failed = {
            **metadata,
            "status": "baseline_failed",
            "exit_code": baseline_exit_code,
            "finished_at": utc_now(),
        }
        write_json(result_path, failed)
        results.commit()
        raise RuntimeError("baseline grader failed after infrastructure retries")

    copy_checkpoint(workdir, result_dir, "baseline")
    command, env = codex_command(workdir, prompt_for(task), home)
    write_json(
        result_dir / "command.json",
        {
            "argv": command,
            "environment_overrides": {
                key: env[key]
                for key in ("CODEX_HOME", "HOME", "CI", "TERM", "NO_COLOR")
            },
        },
    )
    results.commit()

    stop = threading.Event()
    checkpointer = threading.Thread(
        target=checkpoint_loop,
        args=(stop, workdir, result_dir),
        daemon=True,
    )
    checkpointer.start()
    agent_started = time.monotonic()
    try:
        exit_code = run_logged(command, env, workdir, result_dir / "agent.log")
    finally:
        stop.set()
        checkpointer.join(timeout=10)
    agent_duration_s = time.monotonic() - agent_started
    copy_checkpoint(workdir, result_dir, "agent-final")

    final_grade_log = result_dir / "final-grade.log"
    final_grade_exit_code = run_grade_with_retries(workdir, final_grade_log)

    shutil.copytree(workdir / "submission", result_dir / "submission", dirs_exist_ok=True)
    if (workdir / "scores.jsonl").exists():
        shutil.copy2(workdir / "scores.jsonl", result_dir / "scores.jsonl")

    completed = {
        **metadata,
        "status": "completed" if final_grade_exit_code == 0 else "final_grade_failed",
        "agent_exit_code": exit_code,
        "final_grade_exit_code": final_grade_exit_code,
        "agent_duration_s": round(agent_duration_s, 3),
        "finished_at": utc_now(),
    }
    write_json(result_path, completed)
    results.commit()
    return completed
