# Jcode Bench v1: claude-opus-5 high

Benchmark commit: `unknown`  
Model: `claude-opus-5` with `high` reasoning  
Completed cells: **6/6**

## Summary

- Jcode led Claude Code by **-0.1043** mean final score, a **0.930x** geometric-mean instruction-efficiency difference on the same model.
- Total agent time difference: **+92.39%** (Jcode relative to Claude Code).

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| claude-code | claude-opus-5 | no | float-print | 8.8524 | 8.8545 | 5910.5s | 15 | 0 |
| claude-code | claude-opus-5 | no | json-unescape | 3.0106 | 3.0358 | 4399.4s | 63 | 0 |
| claude-code | claude-opus-5 | no | utf16-transcode | 3.5543 | 3.5664 | 9209.5s | 33 | 0 |
| jcode | claude-opus-5 | no | float-print | 8.7714 | 8.7714 | 10129.4s | 24 | 0 |
| jcode | claude-opus-5 | no | json-unescape | 3.0273 | 3.0478 | 14201.2s | 62 | 0 |
| jcode | claude-opus-5 | no | utf16-transcode | 3.3056 | 3.3099 | 13222.6s | 29 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| claude-code | claude-opus-5 | no | 3 | 5.1391 | 5.1522 | 19519.4s | 0 |
| jcode | claude-opus-5 | no | 3 | 5.0348 | 5.0430 | 37553.1s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
