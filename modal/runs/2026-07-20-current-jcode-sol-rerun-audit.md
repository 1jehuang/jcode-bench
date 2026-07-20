# Current Jcode + GPT-5.6 Sol rerun

- Jcode: `v0.53.34-dev (414da9a4a)` (`414da9a4a6`), binary `825c60f739650f66b3c8fd6c674bb2c830bab57c1f54c5c40c92943c90954fc5`
- Model: `gpt-5.6-sol`, OpenAI API, high reasoning, solo
- Benchmark: `cb8ccbc29ad4f4ce4a3ada2e79e019d06729df7c`, task and grader trees byte-identical to July 19
- Status: **3/3 completed; 3/3 accepted final grades passed**

| Task | Final | Sampled best | Efficiency at best | Agent time | Grades |
|---|---:|---:|---:|---:|---:|
| float-print | +7.1391 | +7.1428 | 141.318x | 34.3m | 19 |
| json-unescape | +2.2062 | +2.2062 | 4.615x | 16.1m | 25 |
| utf16-transcode | +2.0920 | +2.0983 | 4.282x | 17.3m | 32 |

Aggregate sampled-best mean: **+3.8158**, or **14.08x** geometric-mean instruction efficiency.

## Comparison with July 19

| Task | July 19 best | Current best | Delta | Relative efficiency |
|---|---:|---:|---:|---:|
| float-print | +7.8107 | +7.1428 | -0.6679 | 62.9% |
| json-unescape | +2.3055 | +2.2062 | -0.0993 | 93.3% |
| utf16-transcode | +2.1142 | +2.0983 | -0.0159 | 98.9% |

The current rerun's aggregate was **14.08x**, versus **16.87x** on July 19. That is **83.4%** of the prior geometric-mean efficiency.

## Audit notes

- `json-unescape` was transparently preempted by Modal at `2026-07-20T05:13:07Z`. The interrupted physical attempt's best preserved checkpoint was +2.0747. It is excluded. Only the clean automatic retry, final +2.2062, is accepted.
- `float-print` passed `./grade --full` over all 2^32 float bit patterns in 1292.5 seconds, exit 0. The full-gate score was +7.1400.
- Every accepted run used the exact recorded Jcode binary, model route, high reasoning effort, task tree, grader tree, and prompt.

## Interpretation

This rerun did **not** reproduce the July 19 aggregate: 14.08x versus 16.87x using sampled-best scores. Most of the difference came from float-print. Each date has one run per task and the Jcode version changed, so this result is not enough by itself to establish a Jcode regression rather than model sampling variance.
