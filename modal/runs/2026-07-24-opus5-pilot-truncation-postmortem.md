# Claude Opus 5 pilot: jcode output-token truncation

Date: 2026-07-24

## What happened

The first Claude Opus 5 pilot cell (`json-unescape`, jcode solo, 20-hour agent
budget) completed the official grade with a final score of **+2.0433**, which
looked like a near-tie with the checked-in Claude Opus 4.8 row (**+2.0016**).

The run was not a valid capability measurement.

| signal | Opus 4.8 (2026-07-19) | Opus 5 pilot |
|---|---:|---:|
| final score | +2.0016 | +2.0433 |
| grades logged | 41 | 3 |
| active agent time | 37m | 50m |
| fraction of 20h budget used | n/a | 4.2% |

The agent exited cleanly (`agent_exit_code=0`, `agent_timed_out=false`) after
using only 4.2% of its budget.

## Root cause

jcode's Anthropic runtime sent a flat `max_tokens = 32768` for every Claude
model. Of the pilot's 23 token-accounted turns, **4 ended at exactly 32768
output tokens**.

Opus 5 allows 128K output tokens and uses always-on adaptive thinking, so its
thinking plus the visible tool call routinely exceeds 32K. Hitting the ceiling
truncated turns mid-tool-call, and the agent loop then ended early instead of
continuing to iterate on the benchmark.

This is a jcode harness defect, not an Opus 5 capability result. It also
understated every prior Anthropic row that ran close to the cap.

## Fix

`anthropic_max_output_tokens` now derives the budget per model:

- 128K for Opus 5, Opus 4.6-4.8, Sonnet 5, Sonnet 4.6, Fable/Mythos 5
- 64K for Haiku 4.5
- 32K for older/unknown ids (unchanged conservative default)

`JCODE_ANTHROPIC_MAX_TOKENS` still overrides. A regression test asserts no
model's derived budget ever falls below the legacy 32K value.

jcode commit: `b9b1470ad`.

## Confirmation from the rerun

The rerun on the fixed build produced direct evidence that the cap was
structurally binding, not merely close:

- `float-print`, jcode, Opus 5: a single planning turn emitted **46,878 output
  tokens**, of which only ~51 tokens were visible text. The rest was adaptive
  thinking.
- That turn is impossible under a 32,768-token budget. On the old build the
  model's planning pass on the hardest task could not physically complete.
- The next turn on the same cell emitted **78,077 output tokens** to produce a
  4,595-character file, so roughly 77,000 tokens were thinking.
- Both turns are 1.4x to 2.4x the entire old budget. On `float-print`, the
  hardest of the three tasks, Opus 5 could not take a single one of its natural
  reasoning steps under the old cap.
- Across the observed rerun turns, no turn reached the real 128,000 ceiling, so
  the new budget is sufficient rather than merely larger.

## Consequence for this benchmark

The pilot cell is void. Opus 5 cells must be rerun on a jcode build that
includes the fix, and the pinned binary sha256 in the run manifest must match
that build.

Artifacts: `runs/20260724T191005Z-opus5-jcode-json-unescape/` on the
`jcode-bench-v1-results` volume (`agent.log`, `result.json`, `scores.jsonl`).
