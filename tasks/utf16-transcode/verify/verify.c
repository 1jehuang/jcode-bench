// verify.c — exhaustive correctness gate for utf16-transcode.
// 1. every single code unit
// 2. all pairs from a boundary-stratified sample x sample (16.7M),
//    plus ALL surrogate x surrogate pairs (2^20) exactly
// 3. every code unit at positions 0..3 inside valid padding
// 4. 200k seeded random strings across regimes with injected lone surrogates
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <stdatomic.h>

size_t utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out);
size_t ref_utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out);

#define INVALID ((size_t)-1)

static atomic_ullong n_cases;
static atomic_int failed;
static pthread_mutex_t report_mu = PTHREAD_MUTEX_INITIALIZER;

static void fail_report(const uint16_t *in, size_t n, const char *stage) {
    pthread_mutex_lock(&report_mu);
    if (!atomic_exchange(&failed, 1)) {
        fprintf(stderr, "MISMATCH (%s) on %zu units:", stage, n);
        for (size_t i = 0; i < n && i < 24; i++) fprintf(stderr, " %04x", in[i]);
        fprintf(stderr, "\n");
    }
    pthread_mutex_unlock(&report_mu);
}

static int check(const uint16_t *in, size_t n, uint8_t *bs, uint8_t *br, const char *stage) {
    memset(bs, 0xAA, 3 * n + 8);
    memset(br, 0x55, 3 * n + 8);
    size_t rs = utf16_to_utf8(in, n, bs);
    size_t rr = ref_utf16_to_utf8(in, n, br);
    atomic_fetch_add_explicit(&n_cases, 1, memory_order_relaxed);
    if (rs != rr || (rr != INVALID && memcmp(bs, br, rr) != 0)) {
        fail_report(in, n, stage);
        return 0;
    }
    return 1;
}

// boundary-stratified sample of code units: all class edges + strided interior
static uint16_t sample[4096];
static size_t n_sample;

static void build_sample(void) {
    size_t k = 0;
    // all boundaries +-2
    static const uint32_t EDGE[] = {0x0000,0x007F,0x0080,0x07FF,0x0800,
        0xD7FF,0xD800,0xDBFF,0xDC00,0xDFFF,0xE000,0xFFFF};
    for (size_t e = 0; e < sizeof(EDGE)/sizeof(EDGE[0]); e++)
        for (int d = -2; d <= 2; d++) {
            int64_t v = (int64_t)EDGE[e] + d;
            if (v >= 0 && v <= 0xFFFF) sample[k++] = (uint16_t)v;
        }
    // strided interior coverage
    for (uint32_t v = 0; v <= 0xFFFF && k < 4096; v += 17) sample[k++] = (uint16_t)v;
    n_sample = k < 4096 ? k : 4096;
}

typedef struct { int tid, nthreads; } targ_t;

static void *pair_worker(void *argp) {
    targ_t *a = argp;
    uint8_t bs[64], br[64];
    uint16_t s[2];
    // sample x sample
    for (size_t i = a->tid; i < n_sample; i += a->nthreads) {
        if (atomic_load_explicit(&failed, memory_order_relaxed)) return NULL;
        s[0] = sample[i];
        for (size_t j = 0; j < n_sample; j++) {
            s[1] = sample[j];
            if (!check(s, 2, bs, br, "pair")) return NULL;
        }
    }
    // all surrogate x surrogate pairs
    for (uint32_t hi = 0xD800 + a->tid; hi <= 0xDFFF; hi += a->nthreads) {
        if (atomic_load_explicit(&failed, memory_order_relaxed)) return NULL;
        s[0] = (uint16_t)hi;
        for (uint32_t lo = 0xD800; lo <= 0xDFFF; lo++) {
            s[1] = (uint16_t)lo;
            if (!check(s, 2, bs, br, "surrogate-pair")) return NULL;
        }
    }
    return NULL;
}

static void *single_worker(void *argp) {
    targ_t *a = argp;
    uint8_t bs[64], br[64];
    uint16_t s[8];
    for (uint32_t v = a->tid; v <= 0xFFFF; v += a->nthreads) {
        if (atomic_load_explicit(&failed, memory_order_relaxed)) return NULL;
        s[0] = (uint16_t)v;
        if (!check(s, 1, bs, br, "single")) return NULL;
        // embedded at positions 0..3 in valid padding 'A', with a trailing pad
        for (int pos = 0; pos < 4; pos++) {
            size_t n = 5;
            for (size_t q = 0; q < n; q++) s[q] = 'A';
            s[pos] = (uint16_t)v;
            if (!check(s, n, bs, br, "embedded")) return NULL;
        }
    }
    return NULL;
}

// seeded random strings
static uint64_t rng_state;
static uint64_t rng_next(void) {
    uint64_t z = (rng_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

int main(int argc, char **argv) {
    uint64_t seed = 0x6A636F6465ULL;
    if (argc > 1 && strcmp(argv[1], "--full") != 0) seed = strtoull(argv[1], NULL, 0);

    build_sample();
    int nt = 8;
    pthread_t th[8];
    targ_t args[8];
    for (int t = 0; t < nt; t++) { args[t] = (targ_t){t, nt}; pthread_create(&th[t], NULL, single_worker, &args[t]); }
    for (int t = 0; t < nt; t++) pthread_join(th[t], NULL);
    if (atomic_load(&failed)) return 1;
    for (int t = 0; t < nt; t++) pthread_create(&th[t], NULL, pair_worker, &args[t]);
    for (int t = 0; t < nt; t++) pthread_join(th[t], NULL);
    if (atomic_load(&failed)) return 1;

    // random strings (single thread is fine: 200k x ~1.5k units)
    rng_state = seed;
    static uint16_t s[2048];
    static uint8_t bs[3 * 2048 + 16], br[3 * 2048 + 16];
    for (int t = 0; t < 200000; t++) {
        size_t n = 1 + (size_t)(rng_next() % 1500);
        for (size_t i = 0; i < n; i++) {
            unsigned r = (unsigned)(rng_next() % 100);
            if (r < 40) s[i] = (uint16_t)(rng_next() % 0x80);
            else if (r < 60) s[i] = (uint16_t)(0x80 + rng_next() % 0x780);
            else if (r < 80) { uint16_t v; do { v = (uint16_t)(0x800 + rng_next() % 0xF800); } while (v >= 0xD800 && v < 0xE000); s[i] = v; }
            else if (r < 95 && i + 1 < n) {
                s[i] = (uint16_t)(0xD800 + rng_next() % 0x400);
                s[++i] = (uint16_t)(0xDC00 + rng_next() % 0x400);
            }
            else s[i] = (uint16_t)(0xD800 + rng_next() % 0x800); // often lone surrogate
        }
        if (!check(s, n, bs, br, "random")) return 1;
    }

    printf("verify: PASS (%llu cases)\n", (unsigned long long)atomic_load(&n_cases));
    return 0;
}
