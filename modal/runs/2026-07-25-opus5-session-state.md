# Claude Opus 5 on Jcode Bench v1: session state

Last updated: 2026-07-25 05:10 UTC. **Run in progress.**

## What was asked

Benchmark Claude Opus 5 on jcode bench under jcode and Claude Code, publish to
the jcode website if jcode does better, and diagnose if not.

## The original answer, and why it was wrong

The first jcode Opus 5 cell scored **+2.0433** on `json-unescape`, barely above
the published Opus 4.8 row (+2.0016). That looked like Opus 5 being no better
than its predecessor under jcode.

It was a harness defect. jcode sent a flat `max_tokens = 32768` for every Claude
model while Opus 5 allows 128,000, so its reasoning turns were truncated
mid-tool-call. The cell exited cleanly after using **4.2% of a 20-hour budget**
with 3 grades, where Opus 4.8 had produced 41.

## jcode defects found and fixed (all on origin/master)

| # | defect | impact |
|---|---|---|
| 1 | `claude-opus-5` missing from the catalog | clean-HOME sessions silently ran `claude-fable-5` |
| 2 | flat 32K output cap for all Claude models | truncated Opus 5 mid-tool-call; measured turns up to 96,016 tokens |
| 3 | `message_end` dropped the provider stop reason | truncation was invisible and jcode's own `max_tokens` recovery could never fire |
| 4 | empty post-tool retry budget of 1 | one transient empty response ended a 20-hour run and reported success |
| 5 | no regression coverage for either recovery path | both failures could silently return |

Defect 3 is the one that made a broken run look healthy: all 23 `message_end`
events in the void pilot reported no stop reason at all. Verified fixed live:

```
{"stop_reason":"max_tokens","type":"message_end"}   <- truncation now visible
{"stop_reason":"end_turn","type":"message_end"}    <- continuation fired
```

## Scale of the truncation

Single-turn output maxima on the fixed build:

| task | max single turn | vs the old 32,768 cap |
|---|---:|---:|
| json-unescape | 71,157 | 2.2x |
| float-print | 84,966 | 2.6x |
| utf16-transcode | 96,016 | 2.9x |

Eight of 44 observed turns exceeded the old cap; **zero** reached the real
128,000 ceiling. Every one of those eight is a planning or write step, so the old
build was cutting exactly the work that produces a submission.

## A separate customer billing bug

`PRICES_PER_MTOK` in the subscription router is the sole metering table, and two
rates disagreed with Anthropic's published pricing in opposite directions:

| model | was | actual | effect |
|---|---|---|---|
| `claude-opus-4-8` | $15 / $75 | $5 / $25 | 3x overcharge |
| `claude-fable-5` | $5 / $25 | $10 / $50 | 2x undercharge |

Fixed and pushed with a test that pins the rates and fails on the old values.
**Not deployed**: it changes live billing, so that is a deliberate decision.

## Open decisions

1. **Deploy the billing fix.** Pushed and tested, awaiting a deploy call.
2. **The output cap.** The router still clamps every request to 32,000 output
   tokens, so subscription users hit the same truncation. Raising it is not a
   clean fix, because the worst-case cost reservation scales with the cap. Four
   options are documented in the backend repo's
   `docs/OUTPUT_TOKEN_CAP_DECISION.md`.

## Measurement infrastructure built

A two-stage gate, because this whole exercise showed how easily an invalid run
produces a plausible number:

- **Stage 1** (`validate_opus5_run.py`): per cell, requires the preflight to have
  observed `claude-opus-5`, zero turns at the output ceiling, a zero final-grade
  exit, non-empty scores, and identical pinned artifacts within each harness.
- **Stage 2** (website publisher): refuses to write site data unless stage 1
  passed **and** jcode matched or beat Claude Code.

43 tests cover every refusal path. The gate was verified by replaying the real
void pilot log and by injecting the pilot's failure, which writes no file.

It has already caught three classes of invalid run (output truncation,
empty-response early exit, pinned-artifact drift) and four of my own measurement
errors (global prompt comparison, pin drift blindness, stale-checkpoint score
reads, and a regex that matched the grader's own source template).

## Interim scores (not a result)

| task | jcode | Claude Code |
|---|---:|---:|
| json-unescape | +2.7731 | +3.0358 |
| float-print | +7.6685 | +8.8545 |
| utf16-transcode | +2.6671 | +3.5664 |

Claude Code has **finished** all three cells. jcode is ~35 minutes in with 6, 12,
and 3 grades and roughly 17 hours of budget left, and every task is still
improving. The harnesses also differ strategically: Claude Code grades
constantly (120 grades on `json-unescape`), while jcode front-loads reasoning.

jcode's interim mean of +4.17 already exceeds the published jcode Opus 4.8 mean
of +3.7643, so Opus 5 is genuinely stronger than 4.8 under jcode once the
truncation is fixed. Whether it beats Claude Code is undetermined.

A systemd-supervised watcher will run both gate stages and write
`modal/runs/2026-07-25-opus5-results.md` when the matrix completes.
