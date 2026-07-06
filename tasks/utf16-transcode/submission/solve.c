// solve.c — the given implementation of utf16_to_utf8.
// A clean, correct scalar transcoder of the kind found in mainstream
// libraries. Make it faster. See ../spec.md. Grade with ../grade.
#include <stdint.h>
#include <stddef.h>

#define INVALID ((size_t)-1)

size_t utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out) {
    size_t o = 0;
    for (size_t i = 0; i < n; i++) {
        uint32_t c = in[i];
        if (c < 0x80) {
            out[o++] = (uint8_t)c;
        } else if (c < 0x800) {
            out[o++] = (uint8_t)(0xC0 | (c >> 6));
            out[o++] = (uint8_t)(0x80 | (c & 0x3F));
        } else if (c < 0xD800 || c >= 0xE000) {
            out[o++] = (uint8_t)(0xE0 | (c >> 12));
            out[o++] = (uint8_t)(0x80 | ((c >> 6) & 0x3F));
            out[o++] = (uint8_t)(0x80 | (c & 0x3F));
        } else if (c < 0xDC00) {
            // high surrogate: need a low surrogate next
            if (i + 1 >= n) return INVALID;
            uint32_t lo = in[i + 1];
            if (lo < 0xDC00 || lo >= 0xE000) return INVALID;
            i++;
            uint32_t cp = 0x10000 + ((c - 0xD800) << 10) + (lo - 0xDC00);
            out[o++] = (uint8_t)(0xF0 | (cp >> 18));
            out[o++] = (uint8_t)(0x80 | ((cp >> 12) & 0x3F));
            out[o++] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F));
            out[o++] = (uint8_t)(0x80 | (cp & 0x3F));
        } else {
            return INVALID; // lone low surrogate
        }
    }
    return o;
}
