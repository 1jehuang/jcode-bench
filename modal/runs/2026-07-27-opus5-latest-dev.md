# Jcode Bench v1: claude-opus-5 high

Benchmark commit: `unknown`  
Model: `claude-opus-5` with `high` reasoning  
Completed cells: **3/3**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | claude-opus-5 | no | json-unescape | 3.1041 | 3.1197 | 9685.4s | 35 | 0 |
| jcode | claude-opus-5 | no | float-print | 8.9923 | 8.9923 | 12073.2s | 22 | 0 |
| jcode | claude-opus-5 | no | utf16-transcode | 2.6876 | 2.6945 | 11739.7s | 74 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | claude-opus-5 | no | 3 | 4.9280 | 4.9355 | 33498.4s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
