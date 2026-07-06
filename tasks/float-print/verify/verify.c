// verify.c — correctness gate for float-print.
// For each tested bit pattern:
//   1. run float_print, NUL-terminate, length check
//   2. format check (strict automaton)
//   3. round-trip check: strtof(out) bit-equals input
//   4. shortest check: significant digits used == minimal round-tripping count
//      (minimal count computed independently with snprintf %.*g)
// Modes: default = stratified fast gate (~19M cases), --full = all 2^32.
// Multithreaded. Exit 0 = pass; prints first counterexample otherwise.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include <stdatomic.h>

size_t float_print(float f, char *out);

static atomic_ullong n_cases;
static atomic_int failed;
static pthread_mutex_t report_mu = PTHREAD_MUTEX_INITIALIZER;

// ---- independent minimal-digit oracle ----
static int min_digits(float f) {
    char buf[64];
    for (int p = 1; p <= 9; p++) {
        snprintf(buf, sizeof(buf), "%.*g", p, (double)f);
        if (strtof(buf, NULL) == f) return p;
    }
    return 9;
}

// ---- strict format automaton ----
// -?D+(.D+)?(e[+-]?D+)?  with: no leading zeros on integer part unless it is
// exactly "0"; fraction has no trailing zero; exponent has no leading zero;
// returns significant digit count, or -1 if malformed.
static int check_format(const char *s, size_t n) {
    size_t i = 0;
    if (i < n && s[i] == '-') i++;
    // integer part
    size_t int_start = i;
    while (i < n && s[i] >= '0' && s[i] <= '9') i++;
    size_t int_len = i - int_start;
    if (int_len == 0) return -1;
    if (int_len > 1 && s[int_start] == '0') return -1; // leading zero
    size_t frac_len = 0;
    if (i < n && s[i] == '.') {
        i++;
        size_t fs = i;
        while (i < n && s[i] >= '0' && s[i] <= '9') i++;
        frac_len = i - fs;
        if (frac_len == 0) return -1;
        if (s[i - 1] == '0') return -1; // trailing zero in fraction
    }
    if (i < n && (s[i] == 'e' || s[i] == 'E')) {
        if (s[i] == 'E') return -1; // lowercase only
        i++;
        if (i < n && (s[i] == '+' || s[i] == '-')) i++;
        size_t es = i;
        while (i < n && s[i] >= '0' && s[i] <= '9') i++;
        size_t elen = i - es;
        if (elen == 0) return -1;
        if (elen > 1 && s[es] == '0') return -1; // leading zero in exponent
    }
    if (i != n) return -1;
    // significant digits: all digits of int+frac, minus leading zeros
    // (a leading "0." contributes no significant digit).
    int sig = 0;
    int seen_nonzero = 0;
    for (size_t k = int_start; k < n; k++) {
        char c = s[k];
        if (c == 'e') break;
        if (c < '0' || c > '9') continue;
        if (c != '0') seen_nonzero = 1;
        if (seen_nonzero) sig++;
    }
    // trailing zeros in the integer part are significant-or-not ambiguous
    // (e.g. 100 for 1e2 uses 1 sig digit conceptually but 3 chars). We count
    // shortest by ROUND-TRIPPING at min_digits, so recompute leniently:
    // strip trailing zeros of integer-only outputs when no fraction present.
    return sig ? sig : 1; // "0" -> 1
}

static int sig_digits_lenient(const char *s, size_t n) {
    // significant digits ignoring trailing zeros when there is no '.' or 'e'
    int has_dot = memchr(s, '.', n) != NULL;
    int has_e = memchr(s, 'e', n) != NULL;
    int sig = check_format(s, n);
    if (sig < 0) return -1;
    if (!has_dot && !has_e) {
        // strip trailing zeros: 1200 -> 2 sig digits
        size_t end = n;
        while (end > 1 && s[end - 1] == '0') { end--; sig--; }
    }
    return sig;
}

static int check_one(uint32_t bits, char *msgbuf) {
    float f;
    memcpy(&f, &bits, 4);
    char out[40];
    memset(out, 0x7F, sizeof(out));
    size_t n = float_print(f, out);
    if (n == 0 || n > 31) {
        sprintf(msgbuf, "bad length %zu", n);
        return 0;
    }
    out[n] = '\0';
    // specials
    if (isnan(f)) {
        if (strcmp(out, "nan") != 0) { sprintf(msgbuf, "nan must print 'nan', got '%s'", out); return 0; }
        return 1;
    }
    if (isinf(f)) {
        const char *want = f < 0 ? "-inf" : "inf";
        if (strcmp(out, want) != 0) { sprintf(msgbuf, "inf mismatch: got '%s'", out); return 0; }
        return 1;
    }
    // round trip
    char *endp;
    float back = strtof(out, &endp);
    if (*endp != '\0') { sprintf(msgbuf, "strtof did not consume '%s'", out); return 0; }
    uint32_t backbits;
    memcpy(&backbits, &back, 4);
    if (backbits != bits) {
        sprintf(msgbuf, "round-trip failed: '%s' -> %08x != %08x", out, backbits, bits);
        return 0;
    }
    if (f == 0.0f) return 1; // sign already verified by bit equality
    // format
    const char *body = out[0] == '-' ? out : out;
    int sig = sig_digits_lenient(body, n);
    if (sig < 0) { sprintf(msgbuf, "malformed output '%s'", out); return 0; }
    // shortest
    int md = min_digits(f);
    if (sig > md) {
        sprintf(msgbuf, "not shortest: '%s' uses %d sig digits, %d possible", out, sig, md);
        return 0;
    }
    return 1;
}

static void fail_report(uint32_t bits, const char *msg) {
    pthread_mutex_lock(&report_mu);
    if (!atomic_exchange(&failed, 1)) {
        float f;
        memcpy(&f, &bits, 4);
        fprintf(stderr, "MISMATCH on bits 0x%08x (%g): %s\n", bits, (double)f, msg);
    }
    pthread_mutex_unlock(&report_mu);
}

// ---- work scheduling ----
typedef struct { uint64_t start, end, stride; } range_t;
#define MAX_RANGES 4096
static range_t ranges[MAX_RANGES];
static int n_ranges;
static atomic_int next_range;

static void add_range(uint64_t start, uint64_t end, uint64_t stride) {
    if (n_ranges >= MAX_RANGES) { fprintf(stderr, "range overflow\n"); exit(2); }
    {
        ranges[n_ranges++] = (range_t){start, end, stride};
    }
}

static void *worker(void *arg) {
    (void)arg;
    char msg[256];
    for (;;) {
        int idx = atomic_fetch_add(&next_range, 1);
        if (idx >= n_ranges) return NULL;
        range_t r = ranges[idx];
        for (uint64_t v = r.start; v < r.end; v += r.stride) {
            if (atomic_load_explicit(&failed, memory_order_relaxed)) return NULL;
            if (!check_one((uint32_t)v, msg)) {
                fail_report((uint32_t)v, msg);
                return NULL;
            }
            atomic_fetch_add_explicit(&n_cases, 1, memory_order_relaxed);
        }
    }
}

static const uint32_t *extra_bits;
static size_t extra_n;
static atomic_ulong extra_next;

static void *extra_worker(void *arg) {
    (void)arg;
    char msg[256];
    for (;;) {
        size_t i = atomic_fetch_add(&extra_next, 4096);
        if (i >= extra_n) return NULL;
        size_t end = i + 4096 < extra_n ? i + 4096 : extra_n;
        for (; i < end; i++) {
            if (atomic_load_explicit(&failed, memory_order_relaxed)) return NULL;
            if (!check_one(extra_bits[i], msg)) { fail_report(extra_bits[i], msg); return NULL; }
            atomic_fetch_add_explicit(&n_cases, 1, memory_order_relaxed);
        }
    }
}

static uint64_t rng_state = 0x6A636F6465ULL;
static uint64_t rng_next(void) {
    uint64_t z = (rng_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

int main(int argc, char **argv) {
    int full = 0;
    uint64_t seed = 0x6A636F6465ULL;
    for (int a = 1; a < argc; a++) {
        if (strcmp(argv[a], "--full") == 0) full = 1;
        else seed = strtoull(argv[a], NULL, 0);
    }
    rng_state = seed;

    if (full) {
        // all 2^32 patterns, split into 64 chunks
        for (int k = 0; k < 64; k++)
            add_range((uint64_t)k << 26, (uint64_t)(k + 1) << 26, 1);
    } else {
        // stratified fast gate:
        // every exponent (0..255, both signs) x mantissa stride 512 (2^14 each)
        for (int sgn = 0; sgn < 2; sgn++)
            for (int ex = 0; ex < 256; ex++) {
                uint64_t base = ((uint64_t)sgn << 31) | ((uint64_t)ex << 23);
                add_range(base, base + (1u << 23), 512);
            }
        // all small integers as floats: 0..2^20
        for (int k = 0; k < 8; k++) {
            // convert integer to float bits: do it as its own range trick —
            // handled below via explicit loop range marker (stride 0 unused);
            (void)k;
        }
        // exact boundaries: first/last 4096 mantissas of every exponent
        for (int sgn = 0; sgn < 2; sgn++)
            for (int ex = 0; ex < 256; ex++) {
                uint64_t base = ((uint64_t)sgn << 31) | ((uint64_t)ex << 23);
                add_range(base, base + 4096, 1);
                add_range(base + (1u << 23) - 4096, base + (1u << 23), 1);
            }
    }

    int nthreads = 8;
    pthread_t th[64];
    for (int t = 0; t < nthreads; t++) pthread_create(&th[t], NULL, worker, NULL);
    for (int t = 0; t < nthreads; t++) pthread_join(th[t], NULL);
    if (atomic_load(&failed)) return 1;

    if (!full) {
        // extra passes: small integers exactly + random patterns (threaded)
        size_t n_extra = (1u << 20) + 1 + 2000000;
        uint32_t *extra = malloc(n_extra * 4);
        size_t k = 0;
        for (uint32_t i = 0; i <= (1u << 20); i++) {
            float f = (float)i;
            memcpy(&extra[k++], &f, 4);
        }
        for (int i = 0; i < 2000000; i++) extra[k++] = (uint32_t)rng_next();
        extra_bits = extra; extra_n = n_extra;
        atomic_store(&extra_next, 0);
        for (int t = 0; t < nthreads; t++) pthread_create(&th[t], NULL, extra_worker, NULL);
        for (int t = 0; t < nthreads; t++) pthread_join(th[t], NULL);
        free(extra);
        if (atomic_load(&failed)) return 1;
    }

    printf("verify: PASS (%llu cases%s)\n",
           (unsigned long long)atomic_load(&n_cases), full ? ", FULL 2^32" : "");
    return 0;
}
