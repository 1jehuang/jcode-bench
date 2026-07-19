# Jcode Bench v1: Jcode frontier model matrix

Snapshot: `2026-07-19T07:15:11Z`  
Harness: `jcode v0.51.4-dev (8b39d814e)`, solo, high reasoning, Modal  
Completed cells: **11/12**, all 11 passed the official final correctness grade

| Model | json-unescape | float-print | utf16-transcode | Mean final | Status |
|---|---:|---:|---:|---:|---|
| GPT-5.4 | +1.5710 | +7.0336 | +1.0310 | +3.2119 | 3/3 complete |
| GPT-5.5 | +1.9841 | +7.1957 | +1.3411 | +3.5070 | 3/3 complete |
| Claude Sonnet 5 | +1.2166 | +6.8199 | +1.2383 | +3.0916 | 3/3 complete |
| Claude Fable 5 | +2.8324 | +7.7011 full gate | +2.5514 | pending | 2/3 complete; float live |

Claude Fable 5's live float-print run passed an exhaustive full correctness gate at **+7.7011**. A later non-full-gate sample measured **+8.0297** at 07:09 UTC. The sampled value is reported for progress only and is not ranked as a final score. The official final score remains unknown until the agent stops and the final grader runs.

Score is `log2(given_cost / optimized_cost)`: +1 is 2x, +2 is 4x. See the JSON report for every run ID, final score, intermediate sampled curve, duration, status, and artifact hash.
