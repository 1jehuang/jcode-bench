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
