# Jcode Bench v1: claude-opus-5 low/medium/high

Benchmark commit: `unknown`  
Model: `claude-opus-5` with `low/medium/high` reasoning  
Completed cells: **18/18**

## Summary

- At `low` effort, Jcode trailed Claude Code by **0.2500** mean final score (**0.841x**), with **+4.21%** total agent time.
- At `medium` effort, Jcode trailed Claude Code by **0.2988** mean final score (**0.813x**), with **-23.21%** total agent time.
- At `high` effort, Jcode led Claude Code by **0.1028** mean final score (**1.074x**), with **+233.86%** total agent time.
- `jcode` moved **+0.3624** (**1.286x**) going from `low` to `medium`, spending **+18.89%** agent time.
- `jcode` moved **+0.5904** (**1.506x**) going from `medium` to `high`, spending **+368.72%** agent time.
- `claude-code` moved **+0.4112** (**1.330x**) going from `low` to `medium`, spending **+61.35%** agent time.
- `claude-code` moved **+0.1888** (**1.140x**) going from `medium` to `high`, spending **+7.80%** agent time.
Per the README variance measurement, a single-cell gap under roughly 0.1 is inside run-to-run noise at k=1, so read these effort steps as directional until they are rerun.

## Per-task results

| Agent | Model | Effort | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---|---|---:|---|---:|---:|---:|---:|---:|
| jcode | claude-opus-5 | low | no | json-unescape | 2.5459 | 2.6062 | 2406.3s | 49 | 0 |
| claude-code | claude-opus-5 | low | no | json-unescape | 2.8394 | 2.8432 | 1860.5s | 22 | 0 |
| jcode | claude-opus-5 | low | no | float-print | 7.3183 | 7.3206 | 4913.9s | 25 | 0 |
| claude-code | claude-opus-5 | low | no | float-print | 7.8447 | 7.8447 | 6174.4s | 37 | 0 |
| jcode | claude-opus-5 | low | no | utf16-transcode | 2.7406 | 2.7555 | 3649.9s | 60 | 0 |
| claude-code | claude-opus-5 | low | no | utf16-transcode | 2.6707 | 2.6753 | 2491.9s | 35 | 0 |
| jcode | claude-opus-5 | medium | no | json-unescape | 2.8353 | 2.8477 | 4275.3s | 33 | 0 |
| claude-code | claude-opus-5 | medium | no | json-unescape | 2.8790 | 2.8790 | 3620.4s | 48 | 0 |
| jcode | claude-opus-5 | medium | no | float-print | 7.6934 | 7.7663 | 2686.2s | 6 | 0 |
| claude-code | claude-opus-5 | medium | no | float-print | 8.1298 | 8.1306 | 7232.9s | 34 | 0 |
| jcode | claude-opus-5 | medium | no | utf16-transcode | 3.1633 | 3.1678 | 6080.9s | 46 | 0 |
| claude-code | claude-opus-5 | medium | no | utf16-transcode | 3.5796 | 3.5820 | 6132.0s | 63 | 0 |
| jcode | claude-opus-5 | high | no | json-unescape | 3.2650 | 3.2845 | 13707.9s | 51 | 0 |
| claude-code | claude-opus-5 | high | no | json-unescape | 3.4302 | 3.4380 | 5669.0s | 24 | 0 |
| jcode | claude-opus-5 | high | no | float-print | 9.1052 | 9.1084 | 24238.5s | 27 | 0 |
| claude-code | claude-opus-5 | high | no | float-print | 8.6436 | 8.6456 | 6782.8s | 13 | 0 |
| jcode | claude-opus-5 | high | no | utf16-transcode | 3.0930 | 3.1051 | 23185.5s | 56 | 0 |
| claude-code | claude-opus-5 | high | no | utf16-transcode | 3.0810 | 3.0851 | 5858.5s | 40 | 0 |

## Aggregate results

| Agent | Model | Effort | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---|---|---:|---:|---:|---:|---:|---:|
| claude-code | claude-opus-5 | low | no | 3 | 4.4516 | 4.4544 | 10526.8s | 0 |
| claude-code | claude-opus-5 | medium | no | 3 | 4.8628 | 4.8639 | 16985.3s | 0 |
| claude-code | claude-opus-5 | high | no | 3 | 5.0516 | 5.0562 | 18310.4s | 0 |
| jcode | claude-opus-5 | low | no | 3 | 4.2016 | 4.2274 | 10970.1s | 0 |
| jcode | claude-opus-5 | medium | no | 3 | 4.5640 | 4.5939 | 13042.4s | 0 |
| jcode | claude-opus-5 | high | no | 3 | 5.1544 | 5.1660 | 61131.9s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
