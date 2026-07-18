# Jcode Bench v1: claude-opus-4-8 high

Benchmark commit: `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`  
Model: `claude-opus-4-8` with `high` reasoning  
Completed cells: **1/1**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| opencode | claude-opus-4-8 | no | json-unescape | 1.9991 | 1.9991 | 2562.8s | 83 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| opencode | claude-opus-4-8 | no | 1 | 1.9991 | 1.9991 | 2562.8s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
