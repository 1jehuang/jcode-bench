# Modal harness comparison

This runner executes the three Jcode Bench v1 tasks across the original four
cells plus two opt-in OpenCode cells:

| harness | native multi-agent support |
|---|---|
| Codex CLI 0.144.1 | disabled |
| Codex CLI 0.144.1 | enabled (`features.multi_agent`) |
| Jcode 0.41.1-dev / 825c96f16 | disabled |
| Jcode 0.41.1-dev / 825c96f16 | enabled (`features.swarm`) |
| OpenCode 1.0.203 / GPT-5.6 Sol | default OpenCode tools |
| OpenCode 1.0.203 / Claude Opus 4.8 | default OpenCode tools |

The original cells and `opencode-sol56` use `gpt-5.6-sol`, high reasoning, and
the OpenAI API. `opencode-opus48` uses `claude-opus-4-8` with Anthropic
`output_config.effort=high`. OpenCode is installed from the explicit npm pin
`opencode-ai@1.0.203`; its effective key-free config and version are checked
before the agent starts and persisted as `opencode-preflight.json`.

Every cell uses the historical benchmark prompt, four CPUs, 8 GiB RAM, and at
most eight concurrent helper agents where the harness exposes that setting.
Each run gets its own Modal function and persists metadata, logs,
submission snapshots, `scores.jsonl`, and final grading output to the
`jcode-bench-v1-results` Volume. Runs use single-use containers so failed
Callgrind host probes are never reused for another matrix cell. The deployed
worker uses Modal's `us-west` pool and retries failed baseline host probes or
preempted calls on fresh containers.

## Deploy and run

```bash
set -a
source ~/.config/jcode/openai.env
source ~/.config/jcode/anthropic.env
set +a

modal deploy modal/benchmark_app.py

# Four-cell smoke/pilot on one task.
~/.local/share/uv/tools/modal/bin/python modal/launch.py --mode pilot --task json-unescape

# Twelve independent full runs.
~/.local/share/uv/tools/modal/bin/python modal/launch.py --mode full

# If json-unescape was already used as the accepted pilot, launch the other eight.
~/.local/share/uv/tools/modal/bin/python modal/launch.py --mode full --tasks float-print utf16-transcode

# Paid-run safety gate: launch exactly one OpenCode Sol task first.
~/.local/share/uv/tools/modal/bin/python modal/launch.py \
  --mode pilot --task json-unescape --cells opencode-sol56

# Only after manually verifying the canary's preflight and agent.log, run the rest.
~/.local/share/uv/tools/modal/bin/python modal/launch.py \
  --mode full --tasks float-print utf16-transcode --cells opencode-sol56

# Opus uses the same canary-first sequence.
~/.local/share/uv/tools/modal/bin/python modal/launch.py \
  --mode pilot --task json-unescape --cells opencode-opus48
~/.local/share/uv/tools/modal/bin/python modal/launch.py \
  --mode full --tasks float-print utf16-transcode --cells opencode-opus48

# Non-blocking status check.
~/.local/share/uv/tools/modal/bin/python modal/status.py modal/launches/<manifest>.json

# Validate completed artifacts and generate reports. Exits 2 while cells remain active.
~/.local/share/uv/tools/modal/bin/python modal/collect_results.py \
  modal/runs/2026-07-10-gpt56-sol-high.json \
  --json-output modal/runs/2026-07-10-gpt56-sol-high-results.json \
  --markdown-output modal/runs/2026-07-10-gpt56-sol-high-results.md
```

The OpenAI and Anthropic keys are attached through
`modal.Secret.from_local_environ`; they are not written to the repository,
image, command metadata, logs, or result Volume.

Canonical launch manifests are checked into [`runs/`](runs/). Ad-hoc launcher
manifests remain ignored because failed infrastructure calls may be replaced.

## Codex Ultra rerun

[`codex_ultra_app.py`](codex_ultra_app.py) is an isolated rerun app that keeps
the historical benchmark commit, prompt, Codex version, model, CPU, memory, and
container policy fixed while changing `model_reasoning_effort` from `high` to
`ultra`. It also enables `multi_agent` with eight threads. The result collector
still counts explicit helper events, so an enabled run is not described as a
multi-agent gain unless the captured Codex log contains delegation events.

```bash
set -a
source ~/.config/jcode/openai.env
set +a

modal deploy modal/codex_ultra_app.py
~/.local/share/uv/tools/modal/bin/python modal/codex_ultra_launch.py

# Check the three independent cells without blocking.
~/.local/share/uv/tools/modal/bin/python modal/status.py \
  modal/launches/<timestamp>-codex-ultra-full.json

# Generate the audited result report after all cells stop.
~/.local/share/uv/tools/modal/bin/python modal/collect_results.py \
  modal/launches/<timestamp>-codex-ultra-full.json \
  --json-output modal/runs/<timestamp>-codex-ultra-results.json \
  --markdown-output modal/runs/<timestamp>-codex-ultra-results.md
```

## Claude Opus 5 harness head-to-head

[`opus5_app.py`](opus5_app.py) is an isolated app (`jcode-bench-v1-opus5`) that
compares two agent harnesses on one model, Anthropic `claude-opus-5` through the
Anthropic API, at a caller-selected reasoning effort:

| harness | delegation | version |
|---|---|---|
| jcode | solo (`JCODE_SWARM_ENABLED=false`) | pinned local binary, sha256-verified |
| Claude Code | default built-in `Task` tool | `@anthropic-ai/claude-code@2.1.219` |

Every cell shares the frozen benchmark commit, the historical benchmark prompt,
four CPUs, 8 GiB RAM, `us-west`, single-use containers, a 20-hour agent
wall-clock budget, and a 24-hour Modal function timeout so baseline and final
grading always complete.

Each cell writes a `preflight.json` that records the CLI version and, critically,
the model the harness actually resolved. Both harnesses are probed with a
throwaway prompt before the benchmark starts and the cell aborts if the observed
model is not `claude-opus-5`. This exists because a jcode build without a
`claude-opus-5` catalog entry silently fell back to `claude-fable-5`, which would
have produced a plausible but wrong benchmark row.

```bash
set -a
source ~/.config/jcode/anthropic.env
set +a

# Pin the exact binary. The app refuses to deploy without a matching sha256.
export JCODE_BENCH_JCODE_BIN=/path/to/jcode
export JCODE_BENCH_JCODE_VERSION="$("$JCODE_BENCH_JCODE_BIN" --version)"
export JCODE_BENCH_JCODE_SHA256="$(sha256sum "$JCODE_BENCH_JCODE_BIN" | cut -d' ' -f1)"

modal deploy modal/opus5_app.py

# Canary first: one task, both harnesses.
~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py \
  --mode pilot --task json-unescape

# Then the remaining four cells.
~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py \
  --mode full --tasks float-print utf16-transcode

# Non-blocking status.
~/.local/share/uv/tools/modal/bin/python modal/status.py modal/launches/<manifest>.json

# Report. Exits 2 while cells remain active.
~/.local/share/uv/tools/modal/bin/python modal/collect_results.py \
  modal/launches/<manifest>.json \
  --json-output modal/runs/<date>-opus5-results.json \
  --markdown-output modal/runs/<date>-opus5-results.md
```

### Reasoning-effort sweep

Reasoning effort is a per-call argument, so one deployment serves the whole
sweep and every cell is otherwise byte-identical. The default launch is 18
cells: `low`/`medium`/`high` x `jcode`/`claude-code` x three tasks. The effort is
part of each run id, because two cells sharing a results directory would make the
second one resume the first one's checkpoint.

```bash
# Detached, retrying deploy, pinned to a clean build.
setsid modal/scripts/opus5-effort-sweep.sh &

# Or by hand, after deploying as above:
~/.local/share/uv/tools/modal/bin/python modal/opus5_launch.py \
  --mode full --harnesses jcode claude-code --efforts low medium high
```

The collector keys aggregates on `(agent, swarm, model, reasoning_effort)`, so a
sweep is never averaged across the axis it exists to measure. A swept report adds
a harness comparison per effort plus each harness's movement from one effort to
the next, ordered by capability (`low` < `medium` < `high` < `xhigh` < `max`)
rather than alphabetically.

Read the steps against the variance section of the top-level README: run-to-run
spread at k=1 is roughly 0.1, so an effort step smaller than that is not evidence
of anything on its own.

### Validity gates before publishing

`validate_opus5_run.py` is the publish gate. The pilot showed a cell can pass
the official grade, exit zero, and still be meaningless, so a favorable number
is not publishable until every gate passes:

- the preflight recorded the intended model;
- no turn ended exactly at the model's output ceiling (truncation);
- the official final grade exited zero;
- the cell did not exit cleanly after a trivial slice of its budget;
- all cells agree on commit, prompt, budget, and pinned artifacts (effort is
  excluded when it is the swept variable, and is instead checked per cell against
  the effort that cell was launched with, so a silent effort fallback still voids
  the run).

```bash
~/.local/share/uv/tools/modal/bin/python modal/validate_opus5_run.py \
  modal/runs/2026-07-24-opus5-head-to-head.json
# exit 0 publishable, 1 a gate failed, 2 cells still running
```

Offline tests for the reporting and validation logic:

```bash
~/.local/share/uv/tools/modal/bin/python modal/test_collect_results.py
```

## Multi-model jcode run (20-hour budget)


[`multimodel_app.py`](multimodel_app.py) is a separate Modal app
(`jcode-bench-v1-multimodel`) that runs jcode solo across four frontier
models, each with a 20-hour agent wall-clock budget (24-hour function
timeout so final grading always completes):

| model | provider route | reasoning effort |
|---|---|---|
| gpt-5.4 | openai-api | high |
| gpt-5.5 | openai-api | high |
| claude-sonnet-5 | anthropic-api | high |
| claude-fable-5 | anthropic-api | high |

All four model/provider routes were smoke-tested with a clean `HOME` and
env-only API keys before this runner was committed. The pinned jcode binary
is `v0.51.4-dev (8b39d814e)`.

```bash
set -a
source ~/.config/jcode/openai.env
source ~/.config/jcode/anthropic.env
set +a

modal deploy modal/multimodel_app.py

# Canary first: one model, one task.
~/.local/share/uv/tools/modal/bin/python modal/multimodel_launch.py \
  --mode pilot --task json-unescape --models gpt-5.5

# Full 12-run matrix (4 models x 3 tasks).
~/.local/share/uv/tools/modal/bin/python modal/multimodel_launch.py --mode full

# Status uses the shared status script with the multimodel manifest.
~/.local/share/uv/tools/modal/bin/python modal/status.py modal/launches/<manifest>.json
```
