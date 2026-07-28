# Jcode Bench v1: claude-opus-5 high

Benchmark commit: `unknown`  
Model: `claude-opus-5` with `high` reasoning  
Completed cells: **1/1**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | claude-opus-5 | no | utf16-transcode | 3.1672 | 3.2405 | 16165.1s | 140 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | claude-opus-5 | no | 1 | 3.1672 | 3.2405 | 16165.1s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
