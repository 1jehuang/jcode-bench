# Jcode Bench v1: mixed high

Benchmark commit: `unknown`  
Model: `mixed` with `high` reasoning  
Completed cells: **9/9**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | gpt-5.4 | no | json-unescape | 1.5710 | 1.7019 | 345.7s | 20 | 0 |
| jcode | claude-sonnet-5 | no | json-unescape | 1.2166 | 14.3015 | 2918.5s | 45 | 0 |
| jcode | claude-fable-5 | no | json-unescape | 2.8324 | 2.8390 | 8110.3s | 78 | 0 |
| jcode | gpt-5.4 | no | float-print | 7.0336 | 7.0336 | 2895.5s | 9 | 0 |
| jcode | claude-sonnet-5 | no | float-print | 6.8199 | 6.8199 | 8517.5s | 38 | 0 |
| jcode | claude-fable-5 | no | float-print | 12.0074 | 12.0086 | 23396.6s | 36 | 0 |
| jcode | gpt-5.4 | no | utf16-transcode | 1.0310 | 1.0331 | 474.3s | 22 | 0 |
| jcode | claude-sonnet-5 | no | utf16-transcode | 1.2383 | 1.2561 | 5387.2s | 37 | 0 |
| jcode | claude-fable-5 | no | utf16-transcode | 2.5514 | 2.5515 | 5623.9s | 7 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| jcode | claude-fable-5 | no | 3 | 5.7971 | 5.7997 | 37130.8s | 0 |
| jcode | claude-sonnet-5 | no | 3 | 3.0916 | 7.4592 | 16823.2s | 0 |
| jcode | gpt-5.4 | no | 3 | 3.2119 | 3.2562 | 3715.4s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
