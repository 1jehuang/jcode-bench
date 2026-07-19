# Jcode Bench v1: Jcode frontier model matrix

Snapshot: `2026-07-19T11:45:24Z`
Harness: `jcode v0.51.4-dev (8b39d814e)`, solo, high reasoning, Modal
Completed cells: **18/18**, all 18 passed the official final correctness grade

| Model | json-unescape | float-print | utf16-transcode | Mean final | Status |
|---|---:|---:|---:|---:|---|
| GPT-5.4 | +1.5710 | +7.0336 | +1.0310 | +3.2119 | 3/3 complete |
| GPT-5.5 | +1.9841 | +7.1957 | +1.3411 | +3.5070 | 3/3 complete |
| GPT-5.6 Sol | +2.2900 | +7.8065 | +2.1109 | +4.0691 | 3/3 complete |
| Claude Sonnet 5 | +1.2166 | +6.8199 | +1.2383 | +3.0916 | 3/3 complete |
| Claude Fable 5 | +2.8324 | +12.0074 | +2.5514 | +5.7971 | 3/3 complete |
| Claude Opus 4.8 | +2.0016 | +7.1795 | +2.1117 | +3.7643 | 3/3 complete |

Claude Fable 5 finished with the highest mean final score at **+5.7971**. GPT-5.6 Sol was second at **+4.0691**, and Claude Opus 4.8 was third at **+3.7643**.

Score is `log2(given_cost / optimized_cost)`: +1 is 2x, +2 is 4x. See the JSON report for every run ID, final score, intermediate sampled curve, duration, status, and artifact hash.
