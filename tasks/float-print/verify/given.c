// solve.c — the given implementation of float_print.
// Correct and simple: try increasing digit counts with snprintf until the
// result round-trips. This is what a careful programmer writes first, and
// it is slow. Make it faster. See ../spec.md. Grade with ../grade.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>

size_t given_float_print(float f, char *out) {
    // Specials.
    if (isnan(f)) { memcpy(out, "nan", 3); return 3; }
    if (isinf(f)) {
        if (f < 0) { memcpy(out, "-inf", 4); return 4; }
        memcpy(out, "inf", 3);
        return 3;
    }
    if (f == 0.0f) {
        // preserve sign of zero
        if (signbit(f)) { memcpy(out, "-0", 2); return 2; }
        out[0] = '0';
        return 1;
    }

    // Try shortest first: %.<p>g produces p significant digits.
    char buf[64];
    for (int prec = 1; prec <= 9; prec++) {
        int n = snprintf(buf, sizeof(buf), "%.*g", prec, (double)f);
        if (n <= 0) continue;
        float back = strtof(buf, NULL);
        if (back == f) {
            // normalize: %g may emit exponents like e+05; strip leading
            // zeros in the exponent to keep the format tight (e+05 -> e+5).
            char *e = memchr(buf, 'e', (size_t)n);
            if (e) {
                char *p = e + 1;
                char sign = 0;
                if (*p == '+' || *p == '-') { sign = *p; p++; }
                while (*p == '0' && p[1] != '\0') {
                    memmove(p, p + 1, (size_t)(n - (p - buf)));
                    n--;
                }
                if (sign == '+') {
                    // keep '+'? strtof accepts both; keep as-is (allowed).
                }
            }
            memcpy(out, buf, (size_t)n);
            return (size_t)n;
        }
    }
    // 9 significant digits always round-trips for float32.
    int n = snprintf(buf, sizeof(buf), "%.9g", (double)f);
    memcpy(out, buf, (size_t)n);
    return (size_t)n;
}
