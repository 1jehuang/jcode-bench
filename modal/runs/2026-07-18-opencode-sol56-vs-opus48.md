# OpenCode 1.0.203: GPT-5.6 Sol high vs Claude Opus 4.8 high

Benchmark commit: `a9bfcdd9ed6cba355bef1025b552ee3da70ce2c0`
Score: `log2(given_cost / optimized_cost)`; higher is better.

## Per-task results

| Task | Sol final | Sol best | Opus final | Opus best | Opus−Sol final | Opus−Sol best | Sol time | Opus time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| json-unescape | 2.1774 | 2.1894 | 1.9991 | 1.9991 | -0.1783 | -0.1903 | 27.6m | 42.7m |
| float-print | 7.2141 | 7.2181 | 7.2040 | 7.2077 | -0.0101 | -0.0104 | 36.2m | 95.3m |
| utf16-transcode | 1.5082 | 1.5084 | 1.8526 | 1.8638 | +0.3444 | +0.3554 | 24.7m | 31.5m |

## Aggregate

- Mean final: Sol **3.6332**, Opus **3.6852**. Opus was **+0.0520**, or **1.037x**, higher.
- Mean best: Sol **3.6386**, Opus **3.6902**. Opus was **+0.0516**, or **1.036x**, higher.
- Successful agent time: Sol **88.5m**, Opus **169.5m** (**1.915x**).
- Including the preempted float attempt, observed Opus time was about **253.7m** (**2.868x** Sol).

## Preemption note

- Modal preempted the first Opus float-print container after a full-gate score of **7.2954** and a best sampled score of **7.2973**. The same FunctionCall automatically restarted from scratch.
- If that preempted best is included as the float best, Opus mean best is **3.7201**, **+0.0815** over Sol (**1.058x**).
- Audit: `modal/runs/2026-07-18-opencode-opus48-float-print-preemption.json`.

## Historical Jcode context

- OpenCode Sol mean best **3.6386** vs historical Jcode Sol **3.5129**: **+0.1257** (**1.091x**).
- Historical Jcode Opus mean best was **4.8690** vs OpenCode Opus **3.6902**, but Jcode Opus used **1423m** vs **169.5m** successful OpenCode time and ran on older, mixed harness versions.

## Caveats

- Each OpenCode model has one successful run per task, so model variance is unmeasured.
- Modal preempted the first Opus float-print container after it passed a 7.2954 full gate; the same FunctionCall automatically restarted from scratch. Main Opus aggregate scores use the successful retry, while the preempted best is reported separately.
- Successful agent duration excludes the preempted Opus float-print attempt. Observed time including preemption is an elapsed approximation from container timestamps.
- Historical Jcode Opus runs used much longer, unmatched budgets and older harness/Jcode versions; treat that context as directional, not a controlled agent comparison.

Sources: `modal/runs/2026-07-17-opencode-sol56-results.json`, `modal/runs/2026-07-18-opencode-opus48-results.json`, `modal/runs/2026-07-10-jcode-solo-sol56-vs-opus48.json`
