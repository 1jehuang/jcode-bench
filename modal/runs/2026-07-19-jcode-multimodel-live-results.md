# Jcode Bench v1: Jcode frontier model matrix

Snapshot: `2026-07-19T08:14:10Z`
Harness: `jcode v0.51.4-dev (8b39d814e)`, solo, high reasoning, Modal
Completed cells: **11/15**, all 11 passed the official final correctness grade

| Model | json-unescape | float-print | utf16-transcode | Mean final | Status |
|---|---:|---:|---:|---:|---|
| GPT-5.4 | +1.5710 | +7.0336 | +1.0310 | +3.2119 | 3/3 complete |
| GPT-5.5 | +1.9841 | +7.1957 | +1.3411 | +3.5070 | 3/3 complete |
| GPT-5.6 Sol | running | running (sampled +7.1467) | running | pending | 0/3 complete; 3/3 live |
| Claude Sonnet 5 | +1.2166 | +6.8199 | +1.2383 | +3.0916 | 3/3 complete |
| Claude Fable 5 | +2.8324 | +7.7011 full gate | +2.5514 | pending | 2/3 complete; float live |

Claude Fable 5's live float-print run passed an exhaustive full correctness gate at **+7.7011**. Later non-full-gate samples measured higher, but sampled values are reported for progress only and are not ranked as final. All three matched GPT-5.6 Sol tasks are live; float-print has sampled **+7.1467**, while JSON and UTF-16 have started without score checkpoints yet. Official final scores remain unknown until those agents stop and the final grader runs.

Score is `log2(given_cost / optimized_cost)`: +1 is 2x, +2 is 4x. See the JSON report for every run ID, final score, intermediate sampled curve, duration, status, and artifact hash.
