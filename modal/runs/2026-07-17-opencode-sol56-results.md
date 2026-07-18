# Jcode Bench v1: gpt-5.6-sol high

Benchmark commit: `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`  
Model: `gpt-5.6-sol` with `high` reasoning  
Completed cells: **3/3**

## Summary

No four-way Codex/Jcode comparison is defined for this manifest.

## Per-task results

| Agent | Model | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| opencode | gpt-5.6-sol | no | json-unescape | 2.1774 | 2.1894 | 1655.0s | 25 | 0 |
| opencode | gpt-5.6-sol | no | float-print | 7.2141 | 7.2181 | 2169.3s | 14 | 0 |
| opencode | gpt-5.6-sol | no | utf16-transcode | 1.5082 | 1.5084 | 1484.4s | 19 | 0 |

## Aggregate results

| Agent | Model | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---:|---:|---:|---:|---:|---:|
| opencode | gpt-5.6-sol | no | 3 | 3.6332 | 3.6386 | 5308.7s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
