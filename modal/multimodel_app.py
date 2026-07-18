"""Modal worker for the Jcode Bench v1 multi-model jcode run.

Runs the pinned local jcode build against multiple frontier models
(OpenAI gpt-5.4 / gpt-5.5 via the OpenAI API, Anthropic claude-sonnet-5 /
claude-fable-5 via the Anthropic API), solo mode, on all three tasks.

Deploy with OPENAI_API_KEY and ANTHROPIC_API_KEY in the local environment:

    modal deploy modal/multimodel_app.py

Agents get a 20-hour wall-clock budget; the Modal function timeout is 24h so
baseline and final grading always complete even if the agent uses the full
budget.
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


APP_NAME = "jcode-bench-v1-multimodel"
BENCH_COMMIT = "cb8ccbc29ad4f4ce4a3ada2e79e019d06729df7c"
JCODE_VERSION = "v0.51.4-dev (8b39d814e)"
JCODE_SHA256 = "1b94e8b4e6510d1f585dd7a54bf2d3c9c5adcb407e2323091a7d0fea0224923a"
REASONING_EFFORT = "high"
SWARM_CONCURRENCY = 8
CHECKPOINT_SECONDS = 300
GRADE_ATTEMPTS = 5
AGENT_TIMEOUT_SECONDS = 20 * 60 * 60  # 20 hours of agent wall clock
FUNCTION_TIMEOUT_SECONDS = 24 * 60 * 60  # Modal cap; leaves 4h for grading
TASKS = ("json-unescape", "float-print", "utf16-transcode")

# Model registry: provider routing for the jcode CLI.
MODELS: dict[str, dict[str, str]] = {
    "gpt-5.4": {
        "provider": "openai-api",
        "swarm_route": "openai-api",
        "effort_env": "JCODE_OPENAI_REASONING_EFFORT",
        "vendor": "openai",
    },
    "gpt-5.5": {
        "provider": "openai-api",
        "swarm_route": "openai-api",
        "effort_env": "JCODE_OPENAI_REASONING_EFFORT",
        "vendor": "openai",
    },
    "claude-sonnet-5": {
        "provider": "anthropic-api",
        "swarm_route": "claude-api",
        "effort_env": "JCODE_ANTHROPIC_REASONING_EFFORT",
        "vendor": "anthropic",
    },
    "claude-fable-5": {
        "provider": "anthropic-api",
        "swarm_route": "claude-api",
        "effort_env": "JCODE_ANTHROPIC_REASONING_EFFORT",
        "vendor": "anthropic",
    },
}

ROOT = Path(__file__).resolve().parents[1]
JCODE_BIN = Path(os.environ.get("JCODE_BENCH_JCODE_BIN", Path.home() / ".local/bin/jcode")).resolve()


def _verify_pinned_binary(path: Path) -> None:
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != JCODE_SHA256:
        raise RuntimeError(
            f"jcode binary at {path} has sha256 {digest}, expected pinned {JCODE_SHA256} "
            f"({JCODE_VERSION}). Set JCODE_BENCH_JCODE_BIN to the pinned build."
        )


_verify_pinned_binary(JCODE_BIN)

app = modal.App(APP_NAME)
results = modal.Volume.from_name("jcode-bench-v1-results", create_if_missing=True)
openai_secret = modal.Secret.from_local_environ(["OPENAI_API_KEY"])
anthropic_secret = modal.Secret.from_local_environ(["ANTHROPIC_API_KEY"])

image = (
    modal.Image.from_registry("archlinux:base")
    .run_commands(
        "pacman -Syu --noconfirm --needed base-devel valgrind git jq python",
    )
    .add_local_dir(
        ROOT,
        "/opt/jcode-bench",
        copy=True,
        ignore=[".git", "**/.build", "**/scores.jsonl", "modal/launches"],
    )
    .add_local_file(JCODE_BIN, "/usr/local/bin/jcode", copy=True)
    .run_commands("chmod 0755 /usr/local/bin/jcode")
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
        copy_checkpoint(workdir, result_dir, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))


def prompt_for(task: str) -> str:
    return f"""You are being benchmarked on jcode bench task {task}, in this directory.

Read spec.md. Your job: make submission/solve.c faster. Correctness on every input is a hard gate, verified by ./grade. Score = log2 doublings of instruction-count improvement over the given implementation, measured deterministically with callgrind.

The loop: edit submission/solve.c (you may add more .c/.h files in submission/), run ./grade, read your score. Grade often; every grade is logged to scores.jsonl as your score-over-time curve.

Rules: edit only files under submission/. Self-contained C17, libc only. Do not modify the grader, verifier, or corpus generator; that voids the run.

Work until you genuinely cannot improve further. Aim as high as you can; +1.0 means 2x, +2.0 means 4x. Report your final score."""


def command_for(
    model: str,
    swarm: bool,
    workdir: Path,
    prompt: str,
    home: Path,
) -> tuple[list[str], dict[str, str]]:
    profile = MODELS.get(model)
    if profile is None:
        raise ValueError(f"Unsupported model: {model}")

    env = os.environ.copy()
    env.update({"HOME": str(home), "CI": "1", "TERM": "dumb", "NO_COLOR": "1"})
    env.update(
        {
            "JCODE_PROVIDER": profile["provider"],
            "JCODE_MODEL": model,
            profile["effort_env"]: REASONING_EFFORT,
            "JCODE_SWARM_ENABLED": "true" if swarm else "false",
            "JCODE_SWARM_MODEL": f"{profile['swarm_route']}:{model}",
            "JCODE_SWARM_SPAWN_MODE": "headless",
            "JCODE_SWARM_MAX_CONCURRENT_AGENTS": str(SWARM_CONCURRENCY),
            "JCODE_MEMORY_ENABLED": "false",
        }
    )
    command = [
        "jcode",
        "--no-update",
        "--no-selfdev",
        "-p",
        profile["provider"],
        "-m",
        model,
        "-C",
        str(workdir),
        "run",
        "--ndjson",
        prompt,
    ]
    return command, env


def run_logged_with_budget(
    command: list[str],
    env: dict[str, str],
    cwd: Path,
    log_path: Path,
    budget_seconds: int,
) -> tuple[int, bool]:
    """Run the agent, enforcing the wall-clock budget. Returns (exit_code, timed_out)."""
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
        try:
            return process.wait(timeout=budget_seconds), False
        except subprocess.TimeoutExpired:
            log.write(f"\n=== agent budget of {budget_seconds}s exhausted; terminating ===\n")
            process.terminate()
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=60)
            return process.returncode if process.returncode is not None else -1, True


def run_grade_with_retries(workdir: Path, log_path: Path) -> int:
    """Run the unmodified official grader, retrying only infrastructure crashes."""
    last_returncode = 1
    with log_path.open("w", buffering=1) as log:
        for attempt in range(1, GRADE_ATTEMPTS + 1):
            log.write(f"=== grade attempt {attempt}/{GRADE_ATTEMPTS} ===\n")
            grade = subprocess.run(
                ["./grade"], cwd=workdir, stdout=log, stderr=subprocess.STDOUT, text=True, check=False
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
    secrets=[openai_secret, anthropic_secret],
    volumes={"/results": results},
    timeout=FUNCTION_TIMEOUT_SECONDS,
    cpu=4,
    memory=8192,
    max_containers=12,
    single_use_containers=True,
    region="us-west",
    retries=modal.Retries(max_retries=2, initial_delay=5.0, backoff_coefficient=2.0),
)
def run_case(
    model: str,
    task: str,
    run_id: str,
    swarm: bool = False,
) -> dict[str, object]:
    if model not in MODELS:
        raise ValueError(f"model must be one of {tuple(MODELS)}")
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
        "agent": "jcode",
        "swarm": swarm,
        "task": task,
        "model": model,
        "provider": MODELS[model]["provider"],
        "vendor": MODELS[model]["vendor"],
        "reasoning_effort": REASONING_EFFORT,
        "agent_budget_s": AGENT_TIMEOUT_SECONDS,
        "swarm_concurrency": SWARM_CONCURRENCY,
        "bench_commit": BENCH_COMMIT,
        "jcode_version": JCODE_VERSION,
        "jcode_sha256": JCODE_SHA256,
        "started_at": started_at,
        "prompt": prompt_for(task),
    }
    write_json(result_dir / "metadata.json", metadata)
    results.commit()

    baseline_log = result_dir / "baseline-grade.log"
    baseline_exit_code = run_grade_with_retries(workdir, baseline_log)
    if baseline_exit_code != 0:
        failed = {**metadata, "status": "baseline_failed", "exit_code": baseline_exit_code, "finished_at": utc_now()}
        write_json(result_path, failed)
        results.commit()
        raise RuntimeError("baseline grader failed after infrastructure retries")

    copy_checkpoint(workdir, result_dir, "baseline")
    command, env = command_for(model, swarm, workdir, prompt_for(task), home)
    write_json(result_dir / "command.json", {"argv": command, "environment_overrides": {
        key: env[key]
        for key in sorted(env)
        if key.startswith("JCODE_") or key in {"HOME", "CI", "TERM", "NO_COLOR"}
    }})
    results.commit()

    stop = threading.Event()
    checkpointer = threading.Thread(target=checkpoint_loop, args=(stop, workdir, result_dir), daemon=True)
    checkpointer.start()
    agent_started = time.monotonic()
    try:
        exit_code, timed_out = run_logged_with_budget(
            command, env, workdir, result_dir / "agent.log", AGENT_TIMEOUT_SECONDS
        )
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
        "agent_timed_out": timed_out,
        "final_grade_exit_code": final_grade_exit_code,
        "agent_duration_s": round(agent_duration_s, 3),
        "finished_at": utc_now(),
    }
    write_json(result_path, completed)
    results.commit()
    return completed
