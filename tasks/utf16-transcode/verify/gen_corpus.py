#!/usr/bin/env python3
"""gen_corpus.py — cost corpus for utf16-transcode (~1M units total).
Regimes: ascii 40%, latin/cyrillic 25%, cjk 20%, emoji/supplementary 15%.
Record format: u32 unit count, then u16le units. All records valid UTF-16.
Usage: gen_corpus.py SEED OUTFILE"""
import random, struct, sys

def gen_record(rng, regime, units):
    out = []
    while len(out) < units:
        if regime == "ascii":
            out.extend(rng.randrange(0x20, 0x7F) for _ in range(rng.randrange(20, 80)))
        elif regime == "latin":
            r = rng.random()
            if r < 0.5:
                out.extend(rng.randrange(0x20, 0x7F) for _ in range(rng.randrange(2, 10)))
            else:
                out.extend(rng.randrange(0x80, 0x800) for _ in range(rng.randrange(2, 12)))
        elif regime == "cjk":
            r = rng.random()
            if r < 0.25:
                out.extend(rng.randrange(0x20, 0x7F) for _ in range(rng.randrange(1, 6)))
            else:
                out.extend(rng.randrange(0x4E00, 0x9FFF) for _ in range(rng.randrange(4, 20)))
        else:  # emoji
            r = rng.random()
            if r < 0.4:
                out.extend(rng.randrange(0x20, 0x7F) for _ in range(rng.randrange(1, 8)))
            else:
                for _ in range(rng.randrange(1, 6)):
                    cp = rng.randrange(0x10000, 0x110000)
                    cp -= 0x10000
                    out.append(0xD800 + (cp >> 10))
                    out.append(0xDC00 + (cp & 0x3FF))
    return out[:units + 1] if len(out) > units and 0xD800 <= out[units - 1] <= 0xDBFF else out[:units]

def main():
    seed, path = int(sys.argv[1]), sys.argv[2]
    rng = random.Random(seed)
    plan = [("ascii", 40), ("latin", 25), ("cjk", 20), ("emoji", 15)]
    records = []
    for regime, share in plan:
        total = share * 10000
        done = 0
        while done < total:
            units = rng.randrange(500, 3000)
            rec = gen_record(rng, regime, units)
            # ensure no trailing lone high surrogate
            if rec and 0xD800 <= rec[-1] <= 0xDBFF:
                rec.pop()
            records.append(rec)
            done += len(rec)
    rng.shuffle(records)
    with open(path, "wb") as f:
        for rec in records:
            f.write(struct.pack("<I", len(rec)))
            f.write(struct.pack(f"<{len(rec)}H", *rec))
    print(f"corpus: {len(records)} records, {sum(len(r) for r in records)} units, seed {seed}")

if __name__ == "__main__":
    main()
