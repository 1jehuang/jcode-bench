#!/usr/bin/env python3
"""gen_corpus.py — generate the cost-measurement corpus for json-unescape.

Five escape-density regimes, fixed weights and sizes, seeded. The corpus format
is a sequence of records: 4-byte little-endian length, then that many bytes.
All records are VALID inputs (cost is measured on the accept path; the reject
path is covered by the verifier, and rejecting early is legitimately cheap).

Usage: gen_corpus.py SEED OUTFILE
"""
import random
import struct
import sys

# (name, weight, record_count, record_len_range)
REGIMES = [
    ("plain",      0.40, 120, (1024, 4096)),   # ASCII text, no escapes
    ("light",      0.25, 120, (1024, 4096)),   # ~2% simple escapes
    ("dense",      0.15, 120, (512, 2048)),    # ~30% escapes of all kinds
    ("unicode",    0.12, 120, (512, 2048)),    # \uXXXX heavy (BMP)
    ("surrogate",  0.08, 120, (512, 2048)),    # surrogate pairs heavy
]

SIMPLE = ['\\"', '\\\\', '\\/', '\\b', '\\f', '\\n', '\\r', '\\t']
PLAIN_CHARS = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    " .,:;-_!?'()[]{}<>@#$%^&*+=|~`"
)


def bmp_escape(rng):
    while True:
        v = rng.randrange(0x0000, 0x10000)
        if not (0xD800 <= v <= 0xDFFF):
            return "\\u%04x" % v


def surrogate_pair(rng):
    hi = rng.randrange(0xD800, 0xDC00)
    lo = rng.randrange(0xDC00, 0xE000)
    return "\\u%04x\\u%04x" % (hi, lo)


def gen_record(rng, regime, length):
    out = []
    n = 0
    while n < length:
        r = rng.random()
        if regime == "plain":
            run = rng.randrange(16, 64)
            s = "".join(rng.choice(PLAIN_CHARS) for _ in range(run))
        elif regime == "light":
            if r < 0.98:
                run = rng.randrange(8, 48)
                s = "".join(rng.choice(PLAIN_CHARS) for _ in range(run))
            else:
                s = rng.choice(SIMPLE)
        elif regime == "dense":
            if r < 0.70:
                run = rng.randrange(1, 6)
                s = "".join(rng.choice(PLAIN_CHARS) for _ in range(run))
            elif r < 0.92:
                s = rng.choice(SIMPLE)
            else:
                s = bmp_escape(rng)
        elif regime == "unicode":
            if r < 0.45:
                run = rng.randrange(1, 8)
                s = "".join(rng.choice(PLAIN_CHARS) for _ in range(run))
            else:
                s = bmp_escape(rng)
        else:  # surrogate
            if r < 0.45:
                run = rng.randrange(1, 8)
                s = "".join(rng.choice(PLAIN_CHARS) for _ in range(run))
            elif r < 0.75:
                s = surrogate_pair(rng)
            else:
                s = bmp_escape(rng)
        out.append(s)
        n += len(s)
    return "".join(out).encode("ascii")


def main():
    seed = int(sys.argv[1])
    outfile = sys.argv[2]
    rng = random.Random(seed)
    records = []
    for name, _w, count, (lo, hi) in REGIMES:
        for _ in range(count):
            records.append(gen_record(rng, name, rng.randrange(lo, hi)))
    rng.shuffle(records)
    with open(outfile, "wb") as f:
        for rec in records:
            f.write(struct.pack("<I", len(rec)))
            f.write(rec)
    total = sum(len(r) for r in records)
    print(f"corpus: {len(records)} records, {total} bytes, seed {seed}")


if __name__ == "__main__":
    main()
