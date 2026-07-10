# Modal GPT-5.6 Sol comparison

This runner executes the three Jcode Bench v1 tasks across four cells:

| harness | native multi-agent support |
|---|---|
| Codex CLI 0.144.1 | disabled |
| Codex CLI 0.144.1 | enabled (`features.multi_agent`) |
| Jcode 0.41.1-dev / 825c96f16 | disabled |
| Jcode 0.41.1-dev / 825c96f16 | enabled (`features.swarm`) |

Every cell uses `gpt-5.6-sol`, high reasoning, the OpenAI API, the historical
benchmark prompt, four CPUs, 8 GiB RAM, and at most eight concurrent helper
agents. Each run gets its own Modal function and persists metadata, logs,
submission snapshots, `scores.jsonl`, and final grading output to the
`jcode-bench-v1-results` Volume. Runs use single-use containers so failed
Callgrind host probes are never reused for another matrix cell. The deployed
worker uses Modal's `us-west` pool and retries failed baseline host probes or
preempted calls on fresh containers.

## Deploy and run

```bash
set -a
source ~/.config/jcode/openai.env
set +a

modal deploy modal/benchmark_app.py

# Four-cell smoke/pilot on one task.
~/.local/share/uv/tools/modal/bin/python modal/launch.py --mode pilot --task json-unescape

# Twelve independent full runs.
~/.local/share/uv/tools/modal/bin/python modal/launch.py --mode full

# If json-unescape was already used as the accepted pilot, launch the other eight.
~/.local/share/uv/tools/modal/bin/python modal/launch.py --mode full --tasks float-print utf16-transcode

# Non-blocking status check.
~/.local/share/uv/tools/modal/bin/python modal/status.py modal/launches/<manifest>.json

# Validate completed artifacts and generate reports. Exits 2 while cells remain active.
~/.local/share/uv/tools/modal/bin/python modal/collect_results.py \
  modal/runs/2026-07-10-gpt56-sol-high.json \
  --json-output modal/runs/2026-07-10-gpt56-sol-high-results.json \
  --markdown-output modal/runs/2026-07-10-gpt56-sol-high-results.md
```

The OpenAI key is attached through `modal.Secret.from_local_environ`; it is not
written to the repository, image, command metadata, logs, or result Volume.

Canonical launch manifests are checked into [`runs/`](runs/). Ad-hoc launcher
manifests remain ignored because failed infrastructure calls may be replaced.
