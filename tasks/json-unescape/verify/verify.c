// verify.c — exhaustive correctness gate for json-unescape.
// Compares json_unescape (submission) against ref_json_unescape (oracle) on:
//   1. every string of length 0..MAXL over a 19-byte adversarial alphabet
//   2. all 65536 \uXXXX forms
//   3. all 1048576 surrogate pair combinations
//   4. the above with prefix/suffix padding
//   5. 100000 seeded random long strings across regimes
// Exit 0 = pass. Any mismatch prints the counterexample and exits 1.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

size_t json_unescape(const uint8_t *in, size_t in_len, uint8_t *out);
size_t ref_json_unescape(const uint8_t *in, size_t in_len, uint8_t *out);

#define INVALID ((size_t)-1)

static uint8_t buf_sub[1 << 16];
static uint8_t buf_ref[1 << 16];
static unsigned long long n_cases = 0;

static void dump_hex(const uint8_t *p, size_t n) {
    for (size_t i = 0; i < n; i++) fprintf(stderr, "%02x ", p[i]);
    fprintf(stderr, "\n");
}

static void check(const uint8_t *in, size_t in_len) {
    // Poison output buffers so "forgot to write" mismatches are caught.
    memset(buf_sub, 0xAA, in_len * 3 + 8);
    memset(buf_ref, 0x55, in_len * 3 + 8);
    size_t r_sub = json_unescape(in, in_len, buf_sub);
    size_t r_ref = ref_json_unescape(in, in_len, buf_ref);
    n_cases++;
    if (r_sub != r_ref ||
        (r_ref != INVALID && memcmp(buf_sub, buf_ref, r_ref) != 0)) {
        fprintf(stderr, "MISMATCH on input (%zu bytes): ", in_len);
        dump_hex(in, in_len);
        if (r_ref == INVALID)
            fprintf(stderr, "  expected: INVALID\n");
        else {
            fprintf(stderr, "  expected (%zu bytes): ", r_ref);
            dump_hex(buf_ref, r_ref);
        }
        if (r_sub == INVALID)
            fprintf(stderr, "  got:      INVALID\n");
        else {
            fprintf(stderr, "  got      (%zu bytes): ", r_sub);
            dump_hex(buf_sub, r_sub);
        }
        exit(1);
    }
}

// ---- 1. exhaustive short strings over adversarial alphabet ----
// Covers: every escape kind, truncated escapes, invalid escapes, hex digit
// boundaries (0/9/a/f/A/F and non-hex), surrogate lead bytes via u d 8-9 a-c,
// control byte, '"', high byte.
static const uint8_t ALPHA[] = {
    '\\', '"', '/', 'u', 'b', 'f', 'n', 'r', 't',
    '0', '8', '9', 'a', 'c', 'd', 'A', 'D', 'G', 0x1F, 0xC3
};
#define NA (sizeof(ALPHA))
#define MAXL 5

static void exhaustive_short(void) {
    uint8_t s[MAXL];
    for (int len = 0; len <= MAXL; len++) {
        unsigned long long total = 1;
        for (int k = 0; k < len; k++) total *= NA;
        for (unsigned long long idx = 0; idx < total; idx++) {
            unsigned long long v = idx;
            for (int k = 0; k < len; k++) {
                s[k] = ALPHA[v % NA];
                v /= NA;
            }
            check(s, (size_t)len);
        }
    }
}

// ---- 2. all \uXXXX ----
static const char HEXCHARS[] = "0123456789abcdefABCDEF"; // 22 incl. case
static void all_u_forms(void) {
    uint8_t s[6] = {'\\', 'u', 0, 0, 0, 0};
    // all 16^4 lowercase+digit combos, plus uppercase sweep per digit position
    for (unsigned v = 0; v < 0x10000; v++) {
        static const char H[] = "0123456789abcdef";
        s[2] = (uint8_t)H[(v >> 12) & 15];
        s[3] = (uint8_t)H[(v >> 8) & 15];
        s[4] = (uint8_t)H[(v >> 4) & 15];
        s[5] = (uint8_t)H[v & 15];
        check(s, 6);
    }
    // uppercase hex digits exercised combinatorially over a smaller sweep
    for (unsigned v = 0; v < 0x10000; v += 257) {
        static const char H[] = "0123456789ABCDEF";
        s[2] = (uint8_t)H[(v >> 12) & 15];
        s[3] = (uint8_t)H[(v >> 8) & 15];
        s[4] = (uint8_t)H[(v >> 4) & 15];
        s[5] = (uint8_t)H[v & 15];
        check(s, 6);
    }
}

// ---- 3. all surrogate pairs ----
static void all_surrogate_pairs(void) {
    static const char H[] = "0123456789abcdef";
    uint8_t s[12] = {'\\', 'u', 0, 0, 0, 0, '\\', 'u', 0, 0, 0, 0};
    for (unsigned hi = 0xD800; hi <= 0xDBFF; hi++) {
        s[2] = (uint8_t)H[(hi >> 12) & 15];
        s[3] = (uint8_t)H[(hi >> 8) & 15];
        s[4] = (uint8_t)H[(hi >> 4) & 15];
        s[5] = (uint8_t)H[hi & 15];
        for (unsigned lo = 0xDC00; lo <= 0xDFFF; lo++) {
            s[8]  = (uint8_t)H[(lo >> 12) & 15];
            s[9]  = (uint8_t)H[(lo >> 8) & 15];
            s[10] = (uint8_t)H[(lo >> 4) & 15];
            s[11] = (uint8_t)H[lo & 15];
            check(s, 12);
        }
    }
    // high surrogate followed by every possible second code unit (invalid lows)
    for (unsigned lo = 0; lo < 0x10000; lo += 7) {
        s[2] = 'd'; s[3] = '8'; s[4] = '0'; s[5] = '0';
        s[8]  = (uint8_t)H[(lo >> 12) & 15];
        s[9]  = (uint8_t)H[(lo >> 8) & 15];
        s[10] = (uint8_t)H[(lo >> 4) & 15];
        s[11] = (uint8_t)H[lo & 15];
        check(s, 12);
    }
}

// ---- 4. padding contexts ----
static void with_padding(void) {
    // every 2-char alphabet pair embedded in plain runs of varying length
    uint8_t s[80];
    static const size_t PADS[] = {1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33};
    for (size_t pi = 0; pi < sizeof(PADS) / sizeof(PADS[0]); pi++) {
        size_t pad = PADS[pi];
        for (size_t a = 0; a < NA; a++) {
            for (size_t b = 0; b < NA; b++) {
                size_t n = 0;
                for (size_t k = 0; k < pad; k++) s[n++] = 'x';
                s[n++] = ALPHA[a];
                s[n++] = ALPHA[b];
                for (size_t k = 0; k < pad; k++) s[n++] = 'y';
                check(s, n);
            }
        }
    }
}

// ---- 5. seeded random long strings ----
static uint64_t rng_state;
static uint64_t rng_next(void) {
    // splitmix64
    uint64_t z = (rng_state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static size_t gen_random(uint8_t *s, size_t maxlen) {
    size_t target = 1 + (size_t)(rng_next() % maxlen);
    size_t n = 0;
    static const char H[] = "0123456789abcdefABCDEF";
    while (n + 12 < target) {
        unsigned r = (unsigned)(rng_next() % 100);
        if (r < 55) {
            // plain run
            size_t run = 1 + (size_t)(rng_next() % 24);
            for (size_t k = 0; k < run && n + 1 < target; k++) {
                uint8_t c;
                do { c = (uint8_t)(0x20 + (rng_next() % 0xE0)); }
                while (c == '"' || c == '\\');
                s[n++] = c;
            }
        } else if (r < 75) {
            // simple escape (sometimes invalid)
            static const char E[] = "\"\\/bfnrtuxq0";
            s[n++] = '\\';
            s[n++] = (uint8_t)E[rng_next() % (sizeof(E) - 1)];
        } else if (r < 90) {
            // \uXXXX with random hex-ish chars (sometimes non-hex)
            s[n++] = '\\';
            s[n++] = 'u';
            for (int k = 0; k < 4; k++) {
                if (rng_next() % 20 == 0)
                    s[n++] = (rng_next() & 1) ? 'g' : 'G'; // invalid hex, both cases
                else s[n++] = (uint8_t)H[rng_next() % 22];
            }
        } else if (r < 97) {
            // surrogate-ish pair
            unsigned hi = 0xD800 + (unsigned)(rng_next() % 0x400);
            unsigned lo = (rng_next() % 8 == 0)
                              ? (unsigned)(rng_next() % 0x10000)   // often invalid
                              : 0xDC00 + (unsigned)(rng_next() % 0x400);
            static const char h[] = "0123456789abcdef";
            s[n++] = '\\'; s[n++] = 'u';
            s[n++] = (uint8_t)h[(hi >> 12) & 15]; s[n++] = (uint8_t)h[(hi >> 8) & 15];
            s[n++] = (uint8_t)h[(hi >> 4) & 15];  s[n++] = (uint8_t)h[hi & 15];
            s[n++] = '\\'; s[n++] = 'u';
            s[n++] = (uint8_t)h[(lo >> 12) & 15]; s[n++] = (uint8_t)h[(lo >> 8) & 15];
            s[n++] = (uint8_t)h[(lo >> 4) & 15];  s[n++] = (uint8_t)h[lo & 15];
        } else {
            // invalid raw byte
            s[n++] = (uint8_t)(rng_next() % 0x20);
        }
    }
    return n;
}

static void random_long(uint64_t seed, int count) {
    rng_state = seed;
    static uint8_t s[4096];
    for (int t = 0; t < count; t++) {
        size_t n = gen_random(s, sizeof(s) - 16);
        check(s, n);
    }
}

int main(int argc, char **argv) {
    uint64_t seed = 0x6A636F6465ULL; // fixed default; grade passes its seed
    if (argc > 1) seed = strtoull(argv[1], NULL, 0);
    exhaustive_short();
    all_u_forms();
    all_surrogate_pairs();
    with_padding();
    random_long(seed, 100000);
    printf("verify: PASS (%llu cases)\n", n_cases);
    return 0;
}
