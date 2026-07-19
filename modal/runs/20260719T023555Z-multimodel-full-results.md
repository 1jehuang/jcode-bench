# Jcode Bench v1: mixed high

Benchmark commit: `unknown`  
Model: `mixed` with `high` reasoning  
Completed cells: **2/2**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | gpt-5.5 | no | float-print | 7.1957 | 7.2042 | 3126.6s | 23 | 0 |
| jcode | gpt-5.5 | no | utf16-transcode | 1.3411 | 1.3411 | 397.7s | 17 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | gpt-5.5 | no | 2 | 4.2684 | 4.2727 | 3524.3s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
