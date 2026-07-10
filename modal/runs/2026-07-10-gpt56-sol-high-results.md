# Jcode Bench v1: GPT-5.6 Sol high

Benchmark commit: `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`  
Model: `gpt-5.6-sol` with `high` reasoning  
Completed cells: **12/12**

## Summary

- Codex led Jcode by **+0.3781** mean score without swarms, a **1.300x** geometric-mean instruction-efficiency advantage.
- With swarms enabled, Codex led by **+0.7187**, a **1.646x** advantage.
- Enabling Codex multi-agent mode changed mean score by **+0.3242** (**1.252x**) and total agent time by **+7.06%**.
- Enabling Jcode swarm mode changed mean score by **-0.0164** (**0.989x**) and total agent time by **-5.55%**.
- All swarm-enabled commands were configured correctly, but captured logs contained **zero explicit native helper events** in every cell. Treat the swarm deltas as enabled-mode outcomes, not demonstrated delegation gains.

## Per-task results

| Agent | Swarm enabled | Task | Final | Best | Agent time | Grades | Explicit helper events |
|---|---:|---|---:|---:|---:|---:|---:|
| codex | no | json-unescape | 2.4228 | 2.4228 | 1189.6s | 21 | 0 |
| codex | yes | json-unescape | 2.6080 | 2.6135 | 1020.1s | 22 | 0 |
| jcode | no | json-unescape | 1.9157 | 1.9173 | 554.4s | 21 | 0 |
| jcode | yes | json-unescape | 1.9172 | 1.9210 | 561.9s | 29 | 0 |
| codex | no | float-print | 7.4165 | 7.4165 | 2531.2s | 30 | 0 |
| codex | yes | float-print | 7.5363 | 7.5363 | 2904.1s | 38 | 0 |
| jcode | no | float-print | 7.1501 | 7.1501 | 2537.0s | 48 | 0 |
| jcode | yes | float-print | 7.1052 | 7.1054 | 2233.6s | 12 | 0 |
| codex | no | utf16-transcode | 1.8319 | 1.8327 | 1008.8s | 24 | 0 |
| codex | yes | utf16-transcode | 2.4996 | 2.5029 | 1139.3s | 29 | 0 |
| jcode | no | utf16-transcode | 1.4711 | 1.4713 | 493.2s | 17 | 0 |
| jcode | yes | utf16-transcode | 1.4653 | 1.4653 | 590.3s | 24 | 0 |

## Aggregate results

| Agent | Swarm enabled | Tasks | Mean final | Mean best | Total agent time | Helper events |
|---|---:|---:|---:|---:|---:|---:|
| codex | no | 3 | 3.8904 | 3.8907 | 4729.6s | 0 |
| codex | yes | 3 | 4.2146 | 4.2176 | 5063.5s | 0 |
| jcode | no | 3 | 3.5123 | 3.5129 | 3584.6s | 0 |
| jcode | yes | 3 | 3.4959 | 3.4972 | 3385.8s | 0 |

`Swarm enabled` records the harness configuration. `Explicit helper events` counts native helper tool events present in the captured agent log, so an enabled cell can legitimately report zero if the model did not invoke helpers.
