#!/usr/bin/env python3
"""Shared grader for jcode bench tasks.

Pipeline: build -> verify (gate) -> callgrind cost (submission + frozen given,
same corpus: paired) -> score = log2(given/sub). Appends to scores.jsonl.

Each task directory provides: submission/*.c, verify/verify.c (+reference.c
optional), verify/given.c (frozen given impl, function prefixed given_),
verify/runner.c (honors -DRUNNER_GIVEN), verify/gen_corpus.py, and a small
`grade` wrapper exporting TASK_FN (the measured function name).
"""
import argparse, json, math, os, re, subprocess, sys, time, glob


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def main(here, fn, extra_cflags=None, verify_args=None):
    SUB = os.path.join(here, "submission")
    VER = os.path.join(here, "verify")
    BUILD = os.path.join(here, ".build")
    CFLAGS = ["-O2", "-std=c17", "-fno-lto", "-g"] + (extra_cflags or [])

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--full", action="store_true",
                    help="run the full exhaustive gate (if the task has one)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    seed = args.seed if args.seed is not None else int(time.time()) % 100000

    os.makedirs(BUILD, exist_ok=True)
    sub_srcs = sorted(glob.glob(os.path.join(SUB, "*.c")))
    if not sub_srcs:
        sys.exit("no .c files in submission/")

    t0 = time.time()
    ref = os.path.join(VER, "reference.c")
    refs = [ref] if os.path.exists(ref) else []
    sh(["cc", *CFLAGS, "-I", SUB, *sub_srcs, *refs,
        os.path.join(VER, "verify.c"), "-o", os.path.join(BUILD, "verify"),
        "-lm", "-lpthread"])
    sh(["cc", *CFLAGS, "-I", SUB, *sub_srcs,
        os.path.join(VER, "runner.c"), "-o", os.path.join(BUILD, "runner"), "-lm"])
    if not os.path.exists(os.path.join(BUILD, "runner_given")):
        sh(["cc", *CFLAGS, "-DRUNNER_GIVEN",
            os.path.join(VER, "given.c"), os.path.join(VER, "runner.c"),
            "-o", os.path.join(BUILD, "runner_given"), "-lm"])
    t_build = time.time() - t0

    t0 = time.time()
    vargs = [str(seed)] + (["--full"] if args.full else []) + (verify_args or [])
    r = subprocess.run([os.path.join(BUILD, "verify"), *vargs],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, end="")
        print(r.stderr, end="", file=sys.stderr)
        print("grade: FAIL (verification)")
        sys.exit(1)
    t_verify = time.time() - t0

    def measure(binary, func):
        corpus = os.path.join(BUILD, f"corpus_{seed}.bin")
        if not os.path.exists(corpus):
            sh(["python3", os.path.join(VER, "gen_corpus.py"), str(seed), corpus])
        cg = os.path.join(BUILD, f"callgrind.{binary}.out")
        if os.path.exists(cg):
            os.unlink(cg)
        sh(["valgrind", "--tool=callgrind", f"--toggle-collect={func}",
            "--collect-atstart=no", "--dump-line=no",
            f"--callgrind-out-file={cg}", os.path.join(BUILD, binary), corpus])
        total = 0
        with open(cg) as f:
            for line in f:
                ls = line.strip()
                if re.match(r"^\d+ \d+$", ls) or re.match(r"^\d+ \d+ ", ls):
                    total += int(ls.split()[1])
        if total == 0:
            sys.exit(f"cost extraction failed (did you rename {func}?)")
        return total

    t0 = time.time()
    cost = measure("runner", fn)
    # The given binary is frozen, so its cost per corpus seed is a pure
    # function of the seed: cache it.
    gcache = os.path.join(BUILD, f"given_cost_{seed}.json")
    if os.path.exists(gcache):
        with open(gcache) as f:
            given = json.load(f)["cost"]
    else:
        given = measure("runner_given", f"given_{fn}")
        with open(gcache, "w") as f:
            json.dump({"cost": given}, f)
    t_measure = time.time() - t0

    score = math.log2(given / cost)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "seed": seed, "cost": cost, "given_cost": given,
           "score": round(score, 4), "full_gate": bool(args.full)}
    with open(os.path.join(here, "scores.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")

    if not args.quiet:
        print(f"build   {t_build:5.1f}s")
        print(f"verify  {t_verify:5.1f}s  PASS{' (FULL gate)' if args.full else ''}")
        print(f"measure {t_measure:5.1f}s  {cost:,} instructions (given: {given:,})")
    print(f"SCORE   {score:+.4f}  ({given / cost:.3f}x)")
