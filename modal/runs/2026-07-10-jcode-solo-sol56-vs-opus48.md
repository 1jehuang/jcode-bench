# Jcode solo: GPT-5.6 Sol vs Claude Opus 4.8

Higher score is better. Scores are `log2(given_cost / optimized_cost)`, so a score difference of 1.0 means a 2x instruction-efficiency difference.

## Final quality

| Task | Sol 5.6 best | Opus 4.8 best | Opus score lead | Opus efficiency factor |
|---|---:|---:|---:|---:|
| json-unescape | 1.9173 | **2.6889** | +0.7716 | **1.707x** |
| float-print | 7.1501 | **8.6385** | +1.4884 | **2.806x** |
| utf16-transcode | 1.4713 | **3.2797** | +1.8084 | **3.503x** |
| **Mean** | 3.5129 | **4.8690** | **+1.3561** | **2.560x** |

On final code quality, Opus won all three tasks. Its geometric-mean output was 2.56x more instruction-efficient than Sol's.

## Time and iteration budget

| Task | Sol time | Opus time | Sol grades | Opus grades | Opus first exceeded Sol's final score |
|---|---:|---:|---:|---:|---:|
| json-unescape | 9.2 min | 158.0 min | 21 | 163 | 12.6 min |
| float-print | 42.3 min | 637.5 min | 48 | 28 | 29.8 min |
| utf16-transcode | 8.2 min | 627.5 min | 17 | 116 | 14.2 min |
| **Total** | **59.7 min** | **1,423.0 min** | **86** | **307** | **56.6 min summed** |

Opus used 23.8x more total active time. However, it first exceeded each Sol final score after 12.6, 29.8, and 14.2 minutes respectively. Those thresholds sum to 56.6 minutes, close to Sol's 59.7-minute total. This suggests the final gap is not only an unlimited-time artifact.

At Sol's own stopping time:

- **json-unescape:** Sol was ahead, 1.9173 vs Opus 1.5413 at 9.2 minutes. Opus passed it at 12.6 minutes.
- **float-print:** Opus was already ahead, reaching 7.4958 by 32.5 minutes versus Sol's final 7.1501 at 42.3 minutes.
- **utf16-transcode:** Sol finished at 8.2 minutes before Opus recorded its first grade. Opus's first grade at 14.2 minutes was 1.5048, already above Sol's final 1.4713.

## Todo and confidence behavior

| Metric | Sol 5.6 | Opus 4.8 |
|---|---:|---:|
| Todo calls | **15** | **0** |
| Total tool calls | 266 | 951 |
| Final todos | 16 across the three runs | none recorded |
| Confidence data | yes | no |

Sol used explicit planning:

- json-unescape: 4 todo updates and 4 final todos, mean final completion confidence **95.5**.
- float-print: 4 updates and 5 final todos, mean final completion confidence **92.6**.
- utf16-transcode: 7 updates and 7 final todos, mean final completion confidence **95.0**.
- All final todos were marked completed. Confidence generally increased monotonically as grades passed.
- Updates were milestone-oriented rather than continuous. The largest gaps were from roughly 30% to 92% of the JSON log, 12% to 85% of float, and 16% to 86% of UTF-16.
- A few intermediate states used completion confidence inconsistently, such as attaching it to an in-progress todo or omitting it when first marking a todo completed. Final states were complete and well-formed.

The persisted Opus Jcode sessions contain no `todo` tool calls and no confidence fields. Opus worked directly through shell, edit, and grading loops. It used 951 tool calls versus Sol's 266.

The important conclusion is that explicit todo/confidence tracking did not correlate with a higher benchmark score in this sample. Sol was more structured and much faster to finish. Opus was substantially more exhaustive and ultimately found much stronger implementations.

## Caveats

1. These are one-run-per-task comparisons, so model variance is unknown.
2. The time budgets were not matched.
3. Opus used Jcode v0.36.x; Sol used Jcode v0.41.1-dev.
4. The Opus json-unescape run used the original json-only benchmark commit before the shared-harness port. Float-print and UTF-16 used the same three-task benchmark commit later pinned for Sol.
5. Best score is used for both models because the published Opus datasets report best score. Sol's final-score results are slightly lower on JSON and UTF-16.

## Sources

- Sol results: [`2026-07-10-gpt56-sol-high-results.json`](2026-07-10-gpt56-sol-high-results.json)
- Sol todo traces: [`2026-07-10-gpt56-sol-high-jcode-solo-todos.md`](2026-07-10-gpt56-sol-high-jcode-solo-todos.md)
- Opus authoritative data: `jcode-website/public/benchmarks/data/jcode-bench-json-unescape-2026-07-05.json` and `jcode-bench-4way-2026-07-06.json`
