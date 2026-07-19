# Jcode Bench v1: Jcode frontier model matrix

Snapshot: `2026-07-19T09:30:19Z`
Harness: `jcode v0.51.4-dev (8b39d814e)`, solo, high reasoning, Modal
Completed cells: **15/15**, all 15 passed the official final correctness grade

| Model | json-unescape | float-print | utf16-transcode | Mean final | Status |
|---|---:|---:|---:|---:|---|
| GPT-5.4 | +1.5710 | +7.0336 | +1.0310 | +3.2119 | 3/3 complete |
| GPT-5.5 | +1.9841 | +7.1957 | +1.3411 | +3.5070 | 3/3 complete |
| GPT-5.6 Sol | +2.2900 | +7.8065 | +2.1109 | +4.0691 | 3/3 complete |
| Claude Sonnet 5 | +1.2166 | +6.8199 | +1.2383 | +3.0916 | 3/3 complete |
| Claude Fable 5 | +2.8324 | +12.0074 | +2.5514 | +5.7971 | 3/3 complete |

Claude Fable 5 finished first by mean final score at **+5.7971**, led by a **+12.0074** final float-print score. GPT-5.6 Sol finished second at **+4.0691**, with final task scores of **+2.2900**, **+7.8065**, and **+2.1109**. Every published cell passed the official final correctness grade.

Score is `log2(given_cost / optimized_cost)`: +1 is 2x, +2 is 4x. See the JSON report for every run ID, final score, intermediate sampled curve, duration, status, and artifact hash.
