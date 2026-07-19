# Jcode Bench v1: mixed high

Benchmark commit: `unknown`  
Model: `mixed` with `high` reasoning  
Completed cells: **1/1**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | gpt-5.6-sol | no | utf16-transcode | 2.1109 | 2.1142 | 750.8s | 18 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | gpt-5.6-sol | no | 1 | 2.1109 | 2.1142 | 750.8s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
