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
| json-unescape | ready | exhaustive | decode JSON string escapes faster |
| float-print | planned | all 2^32 floats | shortest round-trip float to decimal |
| utf16-transcode | planned | exhaustive bounded | UTF-16 <-> UTF-8 |

## Run

```
cd tasks/json-unescape
./grade              # verify exhaustively + score your submission/
```

Edit `submission/solve.c`, re-run `./grade`. That's the whole loop.

Requirements: gcc or clang, valgrind, python3, linux x86-64.

## Rules

- Edit only files in `submission/`.
- No calling out to external processes or libraries from `solve.c`; the function must
  be self-contained C (the verifier links it directly).
- The harness is public and is the official grader. The only thing that would ever be
  withheld from you is nothing.
