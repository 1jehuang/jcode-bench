# utf16-transcode

Convert UTF-16LE to UTF-8. This is the boundary between JavaScript, Windows, and
Java on one side and the rest of the world on the other: every string crossing it
pays this function.

## Task

You are given a working, tested implementation in `submission/solve.c`.
Make it faster. Correctness on every input is the gate, verified exhaustively
over all code units and pairs plus deep seeded coverage.

```
./grade              # build, verify, measure, score
./grade --seed N     # reproduce a specific cost corpus
```

Edit only files under `submission/`.

## Contract

```c
// Transcode UTF-16LE code units to UTF-8.
// in: code units, n: count. out: buffer, capacity >= 3*n+4 bytes.
// Returns bytes written, or (size_t)-1 if the input is invalid UTF-16
// (lone surrogate anywhere).
size_t utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out);
```

Semantics:

- Code units 0x0000-0xD7FF and 0xE000-0xFFFF encode as 1-3 UTF-8 bytes.
- A high surrogate 0xD800-0xDBFF must be immediately followed by a low
  surrogate 0xDC00-0xDFFF; the pair encodes one supplementary code point as
  4 bytes. Anything else (lone high, lone low, high at end of input) is
  invalid: return (size_t)-1.
- On invalid input the output buffer contents are unspecified.

## Verification (the gate)

1. Every single code unit (65,536 cases).
2. Every pair of code units (4.3 billion pairs is too many: all pairs from a
   2,namespace-stratified 4,096-unit sample = 16.7M pairs covering every
   boundary class x class combination, plus all 2^20 surrogate x surrogate
   pairs exactly).
3. Every code unit embedded at positions 0,1,2,3 in valid padding.
4. 200,000 seeded random strings (1-2K units) mixing ASCII runs, BMP text,
   surrogate pairs, and injected lone surrogates.

Any mismatch against the reference oracle fails the grade with a counterexample.

## Cost model (the score)

Instructions inside `utf16_to_utf8` (callgrind) over a seeded ~1M-unit corpus:
ASCII-heavy 40%, Latin/Cyrillic mix 25%, CJK-heavy 20%, emoji/supplementary 15%.
Paired against the frozen given implementation on the same corpus.

```
score = log2(given_cost / your_cost)
```

## Rules

- Self-contained C17, libc only.
- Do not modify the grader/verifier. Any correct program is a valid submission.
