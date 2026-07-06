#!/usr/bin/env python3
"""gen_corpus.py — cost corpus for float-print: 200k float32 bit patterns.
Regimes: uniform bits 30%, round decimals 25%, small ints 15%, [0,1) 15%,
huge/tiny exponents 10%, denormals 5%. Output: raw little-endian uint32s.
Usage: gen_corpus.py SEED OUTFILE"""
import random, struct, sys

def f2b(f):
    return struct.unpack('<I', struct.pack('<f', f))[0]

def main():
    seed, out = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(seed)
    N = 50000
    vals = []
    for _ in range(int(N*0.30)):
        b = rng.getrandbits(32)
        # avoid nan/inf dominating: re-roll exponent 255
        while (b >> 23) & 0xFF == 0xFF:
            b = rng.getrandbits(32)
        vals.append(b)
    for _ in range(int(N*0.25)):
        mant = rng.randrange(1, 10**rng.randrange(1, 7))
        exp = rng.randrange(-6, 7)
        v = float(mant) * (10.0 ** exp)
        vals.append(f2b(struct.unpack('<f', struct.pack('<f', v))[0]))
    for _ in range(int(N*0.15)):
        vals.append(f2b(float(rng.randrange(0, 1 << 20))))
    for _ in range(int(N*0.15)):
        vals.append(f2b(struct.unpack('<f', struct.pack('<f', rng.random()))[0]))
    for _ in range(int(N*0.10)):
        ex = rng.choice(list(range(1, 20)) + list(range(230, 255)))
        b = (rng.getrandbits(1) << 31) | (ex << 23) | rng.getrandbits(23)
        vals.append(b)
    while len(vals) < N:
        vals.append((rng.getrandbits(1) << 31) | rng.getrandbits(23))  # denormal
    rng.shuffle(vals)
    with open(out, 'wb') as f:
        for v in vals:
            f.write(struct.pack('<I', v))
    print(f"corpus: {len(vals)} floats, seed {seed}")

if __name__ == '__main__':
    main()
