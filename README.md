# jcode bench

The first uncontaminatable benchmark. See https://solosystems.dev/bench for the class
definition and https://solosystems.dev/jcode-bench for this instance.

## The idea

Each task hands the agent a working, tested implementation of a real software
primitive, an exhaustive verifier, and a deterministic cost model. The task is one
sentence: **make it faster, it must stay correct on every input, we check all of them.**

- **Quantifiable**: score = log2(given_cost / your_cost), doublings of improvement.
- **Deterministic**: cost = instruction count inside your function (callgrind), not
  wall clock. Same submission, same score, on any machine.
- **Analog**: a continuous score, not pass/fail. The bench discriminates at every
  capability level.
- **Cheat-resistant**: correctness is verified exhaustively (nothing to overfit) and
  the given implementation is the starting line (nothing to look up).
- **Fast to iterate**: `./grade` takes seconds.
- **Pure coding**: real primitives from real libraries.

Time is recorded, not capped. Every grade appends to `scores.jsonl`, producing a
score-over-time curve.

## Tasks

| task | status | verify | one-liner |
|---|---|---|---|
| json-unescape | live | exhaustive | decode JSON string escapes faster |
| float-print | live | all 2^32 floats (--full) | shortest round-trip float to decimal |
| utf16-transcode | live | exhaustive | UTF-16 -> UTF-8 |

## Interpreting scores: run-to-run variance dominates

Two jcode runs of the same task on the same pinned binary, `claude-opus-5`
high, `utf16-transcode`:

| run | final | peak | peak at grade |
|---|---|---|---|
| `20260725T030202Z` | 3.3056 | 3.3099 | 14/27 |
| `20260727T064423Z` | 3.2032* | 3.2123 | 24/27 |

\* still in flight at the time of writing; its curve had been flat within
seed noise for six grades, so the final is not expected to move much.

That is a **0.10 spread from agent behavior alone**, roughly a 0.09 standard
deviation. Separately, regrading one unchanged program across 15 corpus seeds
moves the score by only stdev 0.0040, so measurement noise is ~24x smaller than
run-to-run noise: an agent's search path, not the grader, is what varies.

Consequences for reading a k=1 matrix:

| gap between two harnesses | runs needed to resolve at ~95% |
|---|---|
| 0.25 | k >= 2 |
| 0.08 | k >= 11 |
| 0.02 | k >= 237 |

So a single-cell difference under roughly 0.1 says nothing, and differences
under 0.02 are not worth measuring at any sane cost. Treat k=1 cells as
directional only, and do not attribute a sub-0.1 gap to a harness change
without rerunning. A worked example of getting this wrong: a 0.081
`float-print` gap was investigated as a regression before this variance was
measured, and it sits comfortably inside the spread above.

The trajectory shape is also unstable. The first run peaked at grade 14 of 27
and then flatlined; the second peaked at 24 of 27. Conclusions of the form
"this harness stops searching early" need several runs, since a single curve
does not pin the behavior down.

## Run

```
cd tasks/json-unescape
./grade              # verify exhaustively + score your submission/
```

Edit `submission/solve.c`, re-run `./grade`. That's the whole loop.

Requirements: gcc or clang, valgrind, python3, linux x86-64.

### GPT-5.6 Sol harness comparison

The reproducible Modal runner for Codex versus Jcode, each with native
multi-agent support enabled and disabled, lives in [`modal/`](modal/README.md).
It pins model, reasoning effort, agent versions, resource limits, prompts, and
benchmark commit, and persists logs and checkpoints to a Modal Volume.

The completed 12-cell GPT-5.6 Sol high comparison is available as
[`Markdown`](modal/runs/2026-07-10-gpt56-sol-high-results.md) and
[`JSON`](modal/runs/2026-07-10-gpt56-sol-high-results.json).
The three Jcode-solo todo and confidence traces are also published as
[`Markdown`](modal/runs/2026-07-10-gpt56-sol-high-jcode-solo-todos.md) and
[`JSON`](modal/runs/2026-07-10-gpt56-sol-high-jcode-solo-todos.json).
The Jcode-solo GPT-5.6 Sol versus Opus 4.8 comparison is available as
[`Markdown`](modal/runs/2026-07-10-jcode-solo-sol56-vs-opus48.md) and
[`JSON`](modal/runs/2026-07-10-jcode-solo-sol56-vs-opus48.json).

### Claude Opus 5 reasoning-effort sweep

An 18-cell sweep on 2026-07-28 varies only reasoning effort: `low`, `medium`,
and `high` x Jcode and Claude Code x all three tasks, on one model and one
sha256-pinned Jcode build. All 18 cells passed the validity gate. Results as
[`Markdown`](modal/runs/2026-07-28-opus5-effort-sweep-results.md),
[`JSON`](modal/runs/2026-07-28-opus5-effort-sweep-results.json),
[`validation`](modal/runs/2026-07-28-opus5-effort-sweep-validation.json), and
the [`launch manifest`](modal/runs/2026-07-28-opus5-effort-sweep.json).

| effort | jcode | Claude Code | gap |
|---|---:|---:|---|
| low | 4.2016 | **4.4516** | Claude Code by 0.250 |
| medium | 4.5640 | **4.8628** | Claude Code by 0.299 |
| high | **5.1544** | 5.0516 | Jcode by 0.103, at the noise floor |

Both harnesses convert effort into score monotonically and the ranking flips.
The high-effort gap is the size of the run-to-run spread measured above, so one
run does not resolve it; the low and medium gaps are larger than that spread.
Jcode also spent 17.0 agent hours at high effort against Claude Code's 5.1.

## Rules

- Edit only files in `submission/`.
- No calling out to external processes or libraries from `solve.c`; the function must
  be self-contained C (the verifier links it directly).
- The harness is public and is the official grader. The only thing that would ever be
  withheld from you is nothing.
