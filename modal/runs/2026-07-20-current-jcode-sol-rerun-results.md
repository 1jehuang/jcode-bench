# Jcode Bench v1: gpt-5.6-sol high

Benchmark commit: `cb8ccbc29ad4f4ce4a3ada2e79e019d06729df7c`  
Model: `gpt-5.6-sol` with `high` reasoning  
Completed cells: **3/3**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | gpt-5.6-sol | no | json-unescape | 2.2062 | 2.2062 | 966.0s | 25 | 0 |
| jcode | gpt-5.6-sol | no | float-print | 7.1391 | 7.1428 | 2056.4s | 19 | 0 |
| jcode | gpt-5.6-sol | no | utf16-transcode | 2.0920 | 2.0983 | 1040.9s | 32 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | gpt-5.6-sol | no | 3 | 3.8124 | 3.8158 | 4063.3s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
