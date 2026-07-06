# float-print

Print a float32 as the shortest decimal string that parses back to the same bits.
This is the "shortest round-trip float printing" problem: an active research area
(Grisu 2010, Ryu 2018, Dragonbox 2020), and the printing hot path of every
serializer, REPL, and JSON encoder.

## Task

You are given a working, tested implementation in `submission/solve.c`. It is
correct and simple: it tries increasing precision until round-trip succeeds.
Make it faster. Correctness on every one of the 2^32 float bit patterns is the
gate.

```
./grade              # build, verify (fast gate: ~35M stratified cases), measure, score
./grade --full       # the official gate: all 2^32 bit patterns (multithreaded)
./grade --seed N     # reproduce a specific cost corpus
```

Edit only files under `submission/`.

## Contract

```c
// Write a decimal representation of f into out (buffer >= 32 bytes).
// Returns the number of bytes written (no NUL required).
size_t float_print(float f, char *out);
```

Requirements on the output string, checked per value:

1. **Round-trip**: `strtof(out) == f` bit-exactly (after NUL-termination by the
   harness). For -0.0f the output must parse to -0.0f (sign preserved).
2. **Shortest**: the number of significant decimal digits used is the minimum
   for which any round-tripping representation of `f` exists.
3. **Format**: `-?D(.D+)?(e[+-]?DD?)?` where D are digits, i.e. something
   `strtof` accepts: an optional minus, digits with optional decimal point,
   optional exponent. No leading `+`, no leading zeros on the integer part
   (except a single `0` before `.`), no trailing zeros in the fraction.
   `inf`, `-inf`, `nan` (exactly these, lowercase) for infinities and NaNs.
4. Length <= 31 bytes.

The verifier checks 1, 2 and 4 exactly, and 3 by a strict format automaton.
Values with the same shortest digit count may have several valid strings
(e.g. exponent vs plain notation); any compliant one passes.

## Verification (the gate)

- Default gate (fast, ~seconds, multithreaded): all 2^24 exponent-stratified
  patterns (every exponent x 2^15 mantissa strides), every power of two, every
  exponent boundary +-2, all denormals' boundary region, all NaN/inf classes,
  all values < 2^20 as integers, plus 2M seeded random patterns.
- `--full`: every one of the 2^32 bit patterns. This is the official gate and
  runs in a few minutes on 8 threads. Run it before you claim a final score.

## Cost model (the score)

Instructions inside `float_print` (callgrind), over a seeded corpus of 50k
floats drawn from published regimes (uniform bits 30%, round decimals 25%,
small integers 15%, [0,1) uniforms 15%, huge/tiny exponents 10%, denormals 5%).
Paired: the frozen given implementation (`verify/given.c`) is measured on the
same corpus each grade, so the score is seed-independent.

```
score = log2(given_cost / your_cost)
```

The given implementation is deliberately simple (snprintf try-loop), so early
doublings come easily; the frontier (Ryu/Dragonbox-class, ~few hundred
instructions/call) is worth roughly +6 to +7. Beyond the frontier is research.

## Rules

- Self-contained C17, libc only. You may (and should) replace the snprintf
  approach entirely.
- Do not modify the grader/verifier. Any correct program is a valid submission.
