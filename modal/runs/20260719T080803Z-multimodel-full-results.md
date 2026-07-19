# Jcode Bench v1: mixed high

Benchmark commit: `unknown`  
Model: `mixed` with `high` reasoning  
Completed cells: **3/3**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | gpt-5.6-sol | no | json-unescape | 0.0000 | 0.0000 | 0.3s | 2 | 0 |
| jcode | gpt-5.6-sol | no | float-print | 7.8065 | 7.8107 | 2883.2s | 23 | 0 |
| jcode | gpt-5.6-sol | no | utf16-transcode | 0.0000 | 0.0000 | 0.2s | 2 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | gpt-5.6-sol | no | 3 | 2.6022 | 2.6036 | 2883.7s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
