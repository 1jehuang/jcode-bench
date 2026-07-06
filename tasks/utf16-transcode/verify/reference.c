// reference.c — oracle for utf16-transcode. Defines the semantics.
#include <stdint.h>
#include <stddef.h>

#define INVALID ((size_t)-1)

size_t ref_utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out) {
    size_t o = 0, i = 0;
    while (i < n) {
        uint32_t cu = in[i];
        uint32_t cp;
        if (cu >= 0xD800 && cu <= 0xDBFF) {
            if (i + 1 >= n) return INVALID;
            uint32_t lo = in[i + 1];
            if (!(lo >= 0xDC00 && lo <= 0xDFFF)) return INVALID;
            cp = 0x10000u + ((cu - 0xD800u) * 0x400u) + (lo - 0xDC00u);
            i += 2;
        } else if (cu >= 0xDC00 && cu <= 0xDFFF) {
            return INVALID;
        } else {
            cp = cu;
            i += 1;
        }
        if (cp <= 0x7F) {
            out[o++] = (uint8_t)cp;
        } else if (cp <= 0x7FF) {
            out[o++] = (uint8_t)(0xC0u | (cp >> 6));
            out[o++] = (uint8_t)(0x80u | (cp & 0x3Fu));
        } else if (cp <= 0xFFFF) {
            out[o++] = (uint8_t)(0xE0u | (cp >> 12));
            out[o++] = (uint8_t)(0x80u | ((cp >> 6) & 0x3Fu));
            out[o++] = (uint8_t)(0x80u | (cp & 0x3Fu));
        } else {
            out[o++] = (uint8_t)(0xF0u | (cp >> 18));
            out[o++] = (uint8_t)(0x80u | ((cp >> 12) & 0x3Fu));
            out[o++] = (uint8_t)(0x80u | ((cp >> 6) & 0x3Fu));
            out[o++] = (uint8_t)(0x80u | (cp & 0x3Fu));
        }
    }
    return o;
}
