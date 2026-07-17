"""Modal worker for the Jcode Bench v1 harness comparison.

Deploy with OPENAI_API_KEY and ANTHROPIC_API_KEY in the local environment:

    modal deploy modal/benchmark_app.py

The worker intentionally pins every relevant variable. OpenCode runs use an
inline, key-free config so the effective provider, model, and reasoning options
are persisted without writing API credentials.
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


APP_NAME = "jcode-bench-v1-gpt56"
BENCH_COMMIT = "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0"
CODEX_VERSION = "0.144.1"
JCODE_VERSION = "v0.41.1-dev (825c96f16)"
JCODE_SHA256 = "7038d838daaf4b2185a42e36d88a8b1b327517ba3fc7dfcd507661a3d3129aa0"
OPENCODE_VERSION = "1.0.203"
MODEL = "gpt-5.6-sol"
OPUS_MODEL = "claude-opus-4-8"
REASONING_EFFORT = "high"
SWARM_CONCURRENCY = 8
CHECKPOINT_SECONDS = 300
GRADE_ATTEMPTS = 5
TASKS = ("json-unescape", "float-print", "utf16-transcode")
AGENTS = ("codex", "jcode", "opencode")
OPENCODE_MODELS = {
    MODEL: {
        "provider": "openai",
        "model_options": {
            "reasoningEffort": REASONING_EFFORT,
            "reasoningSummary": "auto",
            "include": ["reasoning.encrypted_content"],
        },
    },
    OPUS_MODEL: {
        "provider": "anthropic",
        # opencode-ai 1.0.203 pins @ai-sdk/anthropic 2.0.50, whose
        # provider options map this to output_config.effort on the wire.
        "model_options": {"effort": REASONING_EFFORT},
    },
}

ROOT = Path(__file__).resolve().parents[1]
JCODE_BIN = Path(os.environ.get("JCODE_BENCH_JCODE_BIN", Path.home() / ".local/bin/jcode")).resolve()

app = modal.App(APP_NAME)
results = modal.Volume.from_name("jcode-bench-v1-results", create_if_missing=True)
openai_secret = modal.Secret.from_local_environ(["OPENAI_API_KEY"])
anthropic_secret = modal.Secret.from_local_environ(["ANTHROPIC_API_KEY"])

image = (
    modal.Image.from_registry("archlinux:base")
    .run_commands(
        "pacman -Syu --noconfirm --needed base-devel valgrind git nodejs npm jq python",
        f"npm install -g @openai/codex@{CODEX_VERSION}",
        f"npm install -g --allow-scripts=opencode-ai opencode-ai@{OPENCODE_VERSION}",
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


def opencode_config(model: str) -> dict[str, object]:
    profile = OPENCODE_MODELS.get(model)
    if profile is None:
        raise ValueError(f"Unsupported OpenCode model: {model}")

    provider = str(profile["provider"])
    model_config: dict[str, object] = {
        "options": profile["model_options"],
    }
    if model == MODEL:
        # gpt-5.6-sol was not yet present in OpenCode's fetched models.dev list
        # when this runner was written, so declare its capabilities explicitly.
        model_config.update(
            {
                "name": "GPT-5.6 Sol",
                "reasoning": True,
                "tool_call": True,
            }
        )

    return {
        "$schema": "https://opencode.ai/config.json",
        "autoupdate": False,
        "share": "disabled",
        "model": f"{provider}/{model}",
        # Non-interactive benchmark containers cannot answer permission prompts.
        "permission": {
            "*": "allow",
            "external_directory": "allow",
        },
        "provider": {
            provider: {
                "models": {
                    model: model_config,
                }
            }
        },
    }


def command_for(
    agent: str,
    swarm: bool,
    workdir: Path,
    prompt: str,
    home: Path,
    model: str = MODEL,
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "CI": "1", "TERM": "dumb", "NO_COLOR": "1"})

    if agent == "codex":
        codex_home = home / ".codex"
        codex_home.mkdir(parents=True, exist_ok=True)
        login = subprocess.run(
            ["codex", "login", "--with-api-key"],
            input=env["OPENAI_API_KEY"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**env, "CODEX_HOME": str(codex_home)},
            timeout=60,
            check=False,
        )
        if login.returncode != 0:
            raise RuntimeError(f"Codex API login failed with exit {login.returncode}")
        env["CODEX_HOME"] = str(codex_home)
        command = [
            "codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-C",
            str(workdir),
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{REASONING_EFFORT}"',
            "-c",
            f"agents.max_threads={SWARM_CONCURRENCY}",
            "-c",
            "agents.max_depth=4",
            "--enable" if swarm else "--disable",
            "multi_agent",
            prompt,
        ]
        return command, env

    if agent == "jcode":
        env.update(
            {
                "JCODE_PROVIDER": "openai-api",
                "JCODE_MODEL": model,
                "JCODE_OPENAI_REASONING_EFFORT": REASONING_EFFORT,
                "JCODE_SWARM_ENABLED": "true" if swarm else "false",
                "JCODE_SWARM_MODEL": f"openai-api:{model}",
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
            "openai-api",
            "-m",
            model,
            "-C",
            str(workdir),
            "run",
            "--ndjson",
            prompt,
        ]
        return command, env

    if agent == "opencode":
        if swarm:
            raise ValueError("OpenCode benchmark cell does not define a swarm mode")
        profile = OPENCODE_MODELS.get(model)
        if profile is None:
            raise ValueError(f"Unsupported OpenCode model: {model}")
        provider = str(profile["provider"])
        env.update(
            {
                "OPENCODE_CONFIG_CONTENT": json.dumps(opencode_config(model), sort_keys=True),
                # Freeze the model catalog bundled into opencode-ai@1.0.203.
                "OPENCODE_DISABLE_MODELS_FETCH": "true",
            }
        )
        command = [
            "opencode",
            "run",
            "--print-logs",
            "--log-level",
            "INFO",
            "--format",
            "json",
            "--model",
            f"{provider}/{model}",
            prompt,
        ]
        return command, env

    raise ValueError(f"Unknown agent: {agent}")


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


def verify_opencode_preflight(model: str, env: dict[str, str], cwd: Path) -> dict[str, object]:
    """Prove the pinned CLI parsed the intended key-free model configuration."""
    version = subprocess.run(
        ["opencode", "--version"],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=60,
    ).stdout.strip()
    if version != OPENCODE_VERSION:
        raise RuntimeError(f"Expected OpenCode {OPENCODE_VERSION}, got {version!r}")

    effective = subprocess.run(
        ["opencode", "debug", "config"],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=60,
    )
    parsed = json.loads(effective.stdout)
    expected = opencode_config(model)
    provider = str(OPENCODE_MODELS[model]["provider"])
    expected_model = f"{provider}/{model}"
    actual_options = parsed["provider"][provider]["models"][model]["options"]
    expected_options = OPENCODE_MODELS[model]["model_options"]
    if parsed.get("model") != expected_model or actual_options != expected_options:
        raise RuntimeError(
            f"OpenCode effective config mismatch: model={parsed.get('model')!r}, "
            f"options={actual_options!r}"
        )

    return {
        "opencode_version": version,
        "provider": provider,
        "model": parsed["model"],
        "reasoning_effort": REASONING_EFFORT,
        "model_options": actual_options,
        "permission": parsed.get("permission"),
        "autoupdate": parsed.get("autoupdate"),
        "share": parsed.get("share"),
        "expected_config": expected,
    }


@app.function(
    image=image,
    secrets=[openai_secret, anthropic_secret],
    volumes={"/results": results},
    timeout=86_400,
    cpu=4,
    memory=8192,
    max_containers=12,
    single_use_containers=True,
    region="us-west",
    retries=modal.Retries(max_retries=3, initial_delay=5.0, backoff_coefficient=2.0),
)
def run_case(
    agent: str,
    swarm: bool,
    task: str,
    run_id: str,
    model: str = MODEL,
) -> dict[str, object]:
    if agent not in AGENTS:
        raise ValueError(f"agent must be one of {AGENTS}")
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    if agent != "opencode" and model != MODEL:
        raise ValueError(f"{agent} only supports {MODEL} in this runner")
    if agent == "opencode" and model not in OPENCODE_MODELS:
        raise ValueError(f"unsupported OpenCode model: {model}")

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
        "agent": agent,
        "swarm": swarm,
        "task": task,
        "model": model,
        "provider": OPENCODE_MODELS[model]["provider"] if agent == "opencode" else "openai",
        "reasoning_effort": REASONING_EFFORT,
        "swarm_concurrency": SWARM_CONCURRENCY,
        "bench_commit": BENCH_COMMIT,
        "codex_version": CODEX_VERSION,
        "jcode_version": JCODE_VERSION,
        "jcode_sha256": JCODE_SHA256,
        "opencode_version": OPENCODE_VERSION,
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
    command, env = command_for(agent, swarm, workdir, prompt_for(task), home, model)
    write_json(result_dir / "command.json", {"argv": command, "environment_overrides": {
        key: env[key]
        for key in sorted(env)
        if key.startswith("JCODE_")
        or key.startswith("OPENCODE_")
        or key in {"CODEX_HOME", "HOME", "CI", "TERM", "NO_COLOR"}
    }})
    if agent == "opencode":
        write_json(result_dir / "opencode-preflight.json", verify_opencode_preflight(model, env, workdir))
    results.commit()

    stop = threading.Event()
    checkpointer = threading.Thread(target=checkpoint_loop, args=(stop, workdir, result_dir), daemon=True)
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
