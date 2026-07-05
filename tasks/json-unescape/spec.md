# json-unescape

Decode JSON string escape sequences. This is the hot path of every JSON parser.

## Task

You are given a working, tested, production-quality implementation in
`submission/solve.c`. Make it faster. It must stay correct on every input.
The verifier checks correctness exhaustively; the grader measures cost as
instructions executed inside your function.

```
./grade            # full loop: build, verify exhaustively, measure, score
./grade --seed 42  # reproduce a specific cost corpus
```

Edit only `submission/solve.c` (you may add extra .c/.h files in `submission/`;
they are compiled and linked automatically).

## Contract

```c
// Decode the body of a JSON string (the bytes between the quotes).
// in / in_len: input bytes. out: output buffer, always large enough
// (caller guarantees capacity >= 3 * in_len + 4).
// Returns number of bytes written, or (size_t)-1 if the input is invalid.
size_t json_unescape(const uint8_t *in, size_t in_len, uint8_t *out);
```

Semantics (RFC 8259):

- Bytes `0x00-0x1F` and `"` (0x22) are invalid anywhere (a JSON string body
  cannot contain them unescaped).
- `\` starts an escape: `\"` `\\` `\/` `\b` `\f` `\n` `\r` `\t` decode to their
  single byte; `\uXXXX` (exactly 4 hex digits, either case) decodes to the code
  point encoded as UTF-8.
- Code points `0xD800-0xDBFF` (high surrogates) must be followed immediately by
  `\uDC00-\uDFFF`; the pair decodes to one supplementary code point (4 UTF-8
  bytes). A lone surrogate (high or low) is invalid.
- Any other byte after `\` is invalid. A trailing `\` or truncated `\uXXX` is
  invalid.
- All other bytes `0x20-0xFF` (except `"` and `\`) pass through unchanged.
  UTF-8 well-formedness of passthrough bytes is NOT checked (matching common
  parser behavior).
- On invalid input, return `(size_t)-1`. Output buffer contents are then
  unspecified.

## Verification (the gate)

`verify.c` compares your function against the reference on:

1. Every string of length 0..5 over a 19-byte adversarial alphabet
   (`\ " / u b f n r t 0 8 9 a c d A D`, 0x1F, 0xC3) — ~2.8M cases covering the
   full escape grammar, truncations, and invalid forms.
2. All 65,536 `\uXXXX` sequences.
3. All 1,048,576 surrogate `\uXXXX\uYYYY` pairs.
4. Each of the above with valid prefix/suffix padding.
5. 100,000 seeded random long strings (1-4KB) mixing all regimes, including
   every invalid-input class.

Any mismatch fails the grade and prints the counterexample. There is no partial
credit for "mostly correct".

## Cost model (the score)

Instructions executed inside `json_unescape` (and callees), counted by
callgrind, over a corpus of ~2MB spanning five escape-density regimes
(plain ASCII, light escapes, dense escapes, unicode-heavy, surrogate-heavy;
weights published in `gen_corpus.py`).

- The corpus is freshly seeded on every grade; memorizing corpus outputs is
  worthless. Scoring is paired: the frozen given implementation
  (`verify/given.c`) is measured on the same corpus in the same grade, so
  corpus difficulty cancels exactly and the score is seed-independent.
  Use `--seed` for exact reproduction.
- One-time table setup in constructors or first-call init is NOT counted
  (real libraries amortize static tables too). Per-call work is counted.
- Instruction count is deterministic and machine-independent for the same
  binary: no wall-clock noise.

```
score = log2(given_cost / your_cost)
```

`0.0` = the given implementation (exactly, on every seed). `+1.0` = twice as
fast. Score history is
appended to `scores.jsonl` on every grade (timestamp, seed, cost, score):
time is recorded, never capped.

## Rules

- `submission/` files must be self-contained C17 (libc only, no external
  libraries, no syscalls in `json_unescape`'s hot path other than nothing:
  the verifier links your function directly and will catch behavioral tricks).
- Any correct program is a valid submission. There is no style requirement.
- The grader in this directory is the official grader.
