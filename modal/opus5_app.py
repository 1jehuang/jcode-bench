"""Modal worker for the Jcode Bench v1 Claude Opus 5 harness comparison.

Runs the three frozen Jcode Bench v1 tasks under two agent harnesses on the
same model (Anthropic `claude-opus-5`, high effort, Anthropic API):

| harness | version | delegation |
|---|---|---|
| jcode | pinned local build | solo (swarm disabled) |
| Claude Code | pinned npm release | default built-in Task tool |

Every cell shares the benchmark commit, prompt, CPU, memory, region, container
policy, model, reasoning effort, and a 20-hour agent wall-clock budget. The
Modal function timeout is 24h so baseline and final grading always complete
even when an agent uses its whole budget.

Deploy with ANTHROPIC_API_KEY in the local environment:

    modal deploy modal/opus5_app.py
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


APP_NAME = "jcode-bench-v1-opus5"
BENCH_COMMIT = "a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0"
MODEL = "claude-opus-5"
REASONING_EFFORT = "high"
# Opus 5's published synchronous max output, verified against the live API
# (max_tokens=128000 is accepted, 128001 is rejected). Recorded per run so the
# collector can detect turns that stopped exactly at the ceiling.
MAX_OUTPUT_TOKENS = 128_000
CLAUDE_CODE_VERSION = "2.1.219"
# Claude Code 2.x ships as a native binary; the npm package only carries a
# Windows shim, so the Linux artifact is fetched directly from Anthropic's
# release channel and pinned by the checksum published in its manifest.
CLAUDE_CODE_PLATFORM = "linux-x64"
CLAUDE_CODE_SHA256 = "22cfd6f5b3061c0391ba84e9cf8c9deaa37783aac18b004d42ec061e98f00691"
CLAUDE_CODE_URL = (
    "https://downloads.claude.ai/claude-code-releases/"
    f"{CLAUDE_CODE_VERSION}/{CLAUDE_CODE_PLATFORM}/claude"
)
# The pinned binary identity is resolved locally at deploy time and baked into
# the image as env vars, so the remote container verifies the exact same
# artifact without the deploy shell's environment leaking in implicitly.
JCODE_VERSION = os.environ.get("JCODE_BENCH_JCODE_VERSION", "")
JCODE_SHA256 = os.environ.get("JCODE_BENCH_JCODE_SHA256", "")
SWARM_CONCURRENCY = 8
CHECKPOINT_SECONDS = 300
GRADE_ATTEMPTS = 5
AGENT_TIMEOUT_SECONDS = 20 * 60 * 60  # 20 hours of agent wall clock
FUNCTION_TIMEOUT_SECONDS = 24 * 60 * 60  # Modal cap; leaves 4h for grading
TASKS = ("json-unescape", "float-print", "utf16-transcode")
HARNESSES = ("jcode", "claude-code")
# Claude Code refuses --dangerously-skip-permissions under root. Modal
# containers are root, so both harnesses drop to this unprivileged account to
# keep the two cells matched on privileges as well as everything else.
BENCH_USER = "bench"

ROOT = Path(__file__).resolve().parents[1]
JCODE_BIN = Path(
    os.environ.get("JCODE_BENCH_JCODE_BIN", Path.home() / ".local/bin/jcode")
).resolve()


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_pinned_binary(path: Path) -> None:
    if not JCODE_SHA256:
        raise RuntimeError(
            "JCODE_BENCH_JCODE_SHA256 must pin the exact jcode binary used for this run"
        )
    digest = _sha256_file(path)
    if digest != JCODE_SHA256:
        raise RuntimeError(
            f"jcode binary at {path} has sha256 {digest}, expected pinned {JCODE_SHA256} "
            f"({JCODE_VERSION!r}). Set JCODE_BENCH_JCODE_BIN to the pinned build."
        )


if modal.is_local():
    if not JCODE_VERSION:
        raise RuntimeError(
            "JCODE_BENCH_JCODE_VERSION must record the exact jcode version for this run"
        )
    _verify_pinned_binary(JCODE_BIN)

app = modal.App(APP_NAME)
results = modal.Volume.from_name("jcode-bench-v1-results", create_if_missing=True)
anthropic_secret = modal.Secret.from_local_environ(["ANTHROPIC_API_KEY"])

image = (
    modal.Image.from_registry("archlinux:base")
    .run_commands(
        "pacman -Syu --noconfirm --needed base-devel valgrind git jq python curl",
        f"curl -fsSL -o /usr/local/bin/claude {CLAUDE_CODE_URL}",
        f'echo "{CLAUDE_CODE_SHA256}  /usr/local/bin/claude" | sha256sum -c -',
        "chmod 0755 /usr/local/bin/claude",
        # Claude Code refuses --dangerously-skip-permissions as root, and Modal
        # containers run as root, so every agent runs as this unprivileged user.
        # Both harnesses use it so the two cells stay matched.
        f"useradd --create-home --shell /bin/bash {BENCH_USER}",
    )
    .add_local_dir(
        ROOT,
        "/opt/jcode-bench",
        copy=True,
        ignore=[".git", "**/.build", "**/scores.jsonl", "modal/launches"],
    )
    .add_local_file(JCODE_BIN, "/usr/local/bin/jcode", copy=True)
    .run_commands("chmod 0755 /usr/local/bin/jcode")
    .env(
        {
            "JCODE_BENCH_JCODE_VERSION": JCODE_VERSION,
            "JCODE_BENCH_JCODE_SHA256": JCODE_SHA256,
        }
    )
)


def _demote() -> "tuple[int, int]":
    """Resolve the unprivileged bench account's uid/gid inside the container."""
    import pwd

    record = pwd.getpwnam(BENCH_USER)
    return record.pw_uid, record.pw_gid


def _chown_tree(path: Path) -> None:
    """Give the bench user ownership of everything it must read and write."""
    uid, gid = _demote()
    os.chown(path, uid, gid)
    for child in path.rglob("*"):
        os.chown(child, uid, gid)


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
        copy_checkpoint(
            workdir, result_dir, datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        )


def prompt_for(task: str) -> str:
    """The historical Jcode Bench v1 benchmark prompt, unchanged."""
    return f"""You are being benchmarked on jcode bench task {task}, in this directory.

Read spec.md. Your job: make submission/solve.c faster. Correctness on every input is a hard gate, verified by ./grade. Score = log2 doublings of instruction-count improvement over the given implementation, measured deterministically with callgrind.

The loop: edit submission/solve.c (you may add more .c/.h files in submission/), run ./grade, read your score. Grade often; every grade is logged to scores.jsonl as your score-over-time curve.

Rules: edit only files under submission/. Self-contained C17, libc only. Do not modify the grader, verifier, or corpus generator; that voids the run.

Work until you genuinely cannot improve further. Aim as high as you can; +1.0 means 2x, +2.0 means 4x. Report your final score."""


def command_for(
    harness: str,
    workdir: Path,
    prompt: str,
    home: Path,
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env.update({"HOME": str(home), "CI": "1", "TERM": "dumb", "NO_COLOR": "1"})

    if harness == "jcode":
        env.update(
            {
                "JCODE_PROVIDER": "anthropic-api",
                "JCODE_MODEL": MODEL,
                "JCODE_ANTHROPIC_REASONING_EFFORT": REASONING_EFFORT,
                "JCODE_SWARM_ENABLED": "false",
                "JCODE_SWARM_MODEL": f"claude-api:{MODEL}",
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
            "anthropic-api",
            "-m",
            MODEL,
            "-C",
            str(workdir),
            "run",
            "--ndjson",
            prompt,
        ]
        return command, env

    if harness == "claude-code":
        env.update(
            {
                "DISABLE_AUTOUPDATER": "1",
                "DISABLE_TELEMETRY": "1",
                "DISABLE_ERROR_REPORTING": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            }
        )
        command = [
            "claude",
            "--print",
            "--model",
            MODEL,
            "--effort",
            REASONING_EFFORT,
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
            prompt,
        ]
        return command, env

    raise ValueError(f"Unknown harness: {harness}")


def run_logged_with_budget(
    command: list[str],
    env: dict[str, str],
    cwd: Path,
    log_path: Path,
    budget_seconds: int,
) -> tuple[int, bool]:
    """Run the agent, enforcing the wall-clock budget. Returns (exit_code, timed_out)."""
    with log_path.open("w", buffering=1) as log:
        uid, gid = _demote()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            user=uid,
            group=gid,
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
            uid, gid = _demote()
            grade = subprocess.run(
                ["./grade"],
                cwd=workdir,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                user=uid,
                group=gid,
            )
            last_returncode = grade.returncode
            if grade.returncode == 0:
                return 0
            log.write(f"grade attempt {attempt} exited {grade.returncode}\n")
            shutil.rmtree(workdir / ".build", ignore_errors=True)
            time.sleep(min(attempt, 3))
    return last_returncode


def _run_captured(command: list[str], env: dict[str, str], cwd: Path, timeout: int) -> str:
    """Run a preflight command, surfacing its captured output on failure.

    A bare CalledProcessError hides the CLI's own diagnostics, which is exactly
    what is needed to tell a broken pin from a broken credential.
    """
    uid, gid = _demote()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
        user=uid,
        group=gid,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"preflight command {command[0]!r} exited {completed.returncode}:\n"
            f"{completed.stdout[-4000:]}"
        )
    return completed.stdout


def verify_preflight(harness: str, env: dict[str, str], cwd: Path) -> dict[str, object]:
    """Prove the pinned CLI is present and resolves the intended model.

    Both harnesses are asked to emit a one-word answer with the exact benchmark
    model and effort. The captured metadata records the model the harness
    actually used, so a silent model fallback can never be mistaken for a real
    benchmark result.
    """
    if harness == "jcode":
        version = _run_captured(["jcode", "--version"], env, cwd, 120).strip()
        probe = _run_captured(
            [
                "jcode",
                "--no-update",
                "--no-selfdev",
                "-p",
                "anthropic-api",
                "-m",
                MODEL,
                "run",
                "--ndjson",
                "Reply with exactly: PREFLIGHT-OK",
            ],
            env,
            cwd,
            600,
        )
        observed_model = None
        for line in probe.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "start":
                observed_model = event.get("model")
                break
        if observed_model != MODEL:
            raise RuntimeError(
                f"jcode resolved model {observed_model!r}, expected {MODEL!r}; "
                "the run would have silently benchmarked a different model"
            )
        return {
            "harness": harness,
            "jcode_version": version,
            "jcode_sha256": _sha256_file(Path("/usr/local/bin/jcode")),
            "observed_model": observed_model,
            "reasoning_effort": REASONING_EFFORT,
            "swarm_enabled": env.get("JCODE_SWARM_ENABLED"),
        }

    version = _run_captured(["claude", "--version"], env, cwd, 120).strip()
    if CLAUDE_CODE_VERSION not in version:
        raise RuntimeError(f"Expected Claude Code {CLAUDE_CODE_VERSION}, got {version!r}")
    probe = _run_captured(
        [
            "claude",
            "--print",
            "--model",
            MODEL,
            "--effort",
            REASONING_EFFORT,
            "--dangerously-skip-permissions",
            "--output-format",
            "stream-json",
            "--verbose",
            "Reply with exactly: PREFLIGHT-OK",
        ],
        env,
        cwd,
        600,
    )
    init_event: dict[str, object] = {}
    for line in probe.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init_event = event
            break
    observed_model = init_event.get("model")
    if observed_model != MODEL:
        raise RuntimeError(
            f"Claude Code resolved model {observed_model!r}, expected {MODEL!r}"
        )
    return {
        "harness": harness,
        "claude_code_version": version,
        "claude_code_sha256": _sha256_file(Path("/usr/local/bin/claude")),
        "observed_model": observed_model,
        "reasoning_effort": REASONING_EFFORT,
        "permission_mode": init_event.get("permissionMode"),
        "api_key_source": init_event.get("apiKeySource"),
        "tools": init_event.get("tools"),
    }


@app.function(
    image=image,
    secrets=[anthropic_secret],
    volumes={"/results": results},
    timeout=FUNCTION_TIMEOUT_SECONDS,
    cpu=4,
    memory=8192,
    max_containers=6,
    single_use_containers=True,
    region="us-west",
    retries=modal.Retries(max_retries=2, initial_delay=5.0, backoff_coefficient=2.0),
)
def run_case(harness: str, task: str, run_id: str) -> dict[str, object]:
    if harness not in HARNESSES:
        raise ValueError(f"harness must be one of {HARNESSES}")
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}")
    _verify_pinned_binary(Path("/usr/local/bin/jcode"))

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

    _chown_tree(work_root)

    result_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "run_id": run_id,
        "status": "running",
        "agent": harness,
        "swarm": False,
        "task": task,
        "model": MODEL,
        "provider": "anthropic-api",
        "vendor": "anthropic",
        "reasoning_effort": REASONING_EFFORT,
        "agent_budget_s": AGENT_TIMEOUT_SECONDS,
        "bench_commit": BENCH_COMMIT,
        "jcode_version": JCODE_VERSION,
        "jcode_sha256": JCODE_SHA256,
        "claude_code_version": CLAUDE_CODE_VERSION,
        "claude_code_sha256": CLAUDE_CODE_SHA256,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "started_at": utc_now(),
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
    command, env = command_for(harness, workdir, prompt_for(task), home)
    write_json(
        result_dir / "command.json",
        {
            "argv": command,
            "environment_overrides": {
                key: env[key]
                for key in sorted(env)
                if key.startswith("JCODE_")
                or key.startswith("CLAUDE_")
                or key.startswith("DISABLE_")
                or key in {"HOME", "CI", "TERM", "NO_COLOR"}
            },
        },
    )
    # Preflight runs in a scratch directory so it cannot touch the task tree.
    preflight_dir = work_root / "preflight"
    preflight_dir.mkdir(parents=True, exist_ok=True)
    _chown_tree(preflight_dir)
    write_json(result_dir / "preflight.json", verify_preflight(harness, env, preflight_dir))
    results.commit()

    stop = threading.Event()
    checkpointer = threading.Thread(
        target=checkpoint_loop, args=(stop, workdir, result_dir), daemon=True
    )
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
