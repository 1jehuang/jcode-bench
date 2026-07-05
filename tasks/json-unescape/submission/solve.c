// solve.c — the given implementation of json_unescape.
// This is your starting point: a clean, production-quality scalar
// implementation of the kind found in mainstream JSON parsers.
// Make it faster. See ../spec.md for the contract. Grade with ../grade.
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define INVALID ((size_t)-1)

// Character class table: 0 = plain passthrough, 1 = backslash, 2 = invalid.
static const uint8_t CLASS[256] = {
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, // 0x00-0x0F
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, // 0x10-0x1F
    0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, // 0x20-0x2F ('"'=0x22)
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, // '\\'=0x5C
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    // 0x80-0xFF: all passthrough
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static int hex_val(uint8_t c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int parse_hex4(const uint8_t *p, unsigned *out) {
    unsigned v = 0;
    for (int k = 0; k < 4; k++) {
        int h = hex_val(p[k]);
        if (h < 0) return -1;
        v = (v << 4) | (unsigned)h;
    }
    *out = v;
    return 0;
}

size_t json_unescape(const uint8_t *in, size_t in_len, uint8_t *out) {
    size_t i = 0, o = 0;
    while (i < in_len) {
        // Copy a run of plain bytes.
        size_t start = i;
        while (i < in_len && CLASS[in[i]] == 0) i++;
        if (i > start) {
            memcpy(out + o, in + start, i - start);
            o += i - start;
        }
        if (i >= in_len) break;
        if (CLASS[in[i]] == 2) return INVALID;
        // Backslash escape.
        if (i + 1 >= in_len) return INVALID;
        uint8_t e = in[i + 1];
        switch (e) {
            case '"':  out[o++] = '"';  i += 2; continue;
            case '\\': out[o++] = '\\'; i += 2; continue;
            case '/':  out[o++] = '/';  i += 2; continue;
            case 'b':  out[o++] = '\b'; i += 2; continue;
            case 'f':  out[o++] = '\f'; i += 2; continue;
            case 'n':  out[o++] = '\n'; i += 2; continue;
            case 'r':  out[o++] = '\r'; i += 2; continue;
            case 't':  out[o++] = '\t'; i += 2; continue;
            case 'u':  break;
            default:   return INVALID;
        }
        // \uXXXX
        if (i + 6 > in_len) return INVALID;
        unsigned cu;
        if (parse_hex4(in + i + 2, &cu) < 0) return INVALID;
        i += 6;
        unsigned cp;
        if (cu >= 0xD800 && cu <= 0xDBFF) {
            if (i + 6 > in_len || in[i] != '\\' || in[i + 1] != 'u')
                return INVALID;
            unsigned lo;
            if (parse_hex4(in + i + 2, &lo) < 0) return INVALID;
            if (lo < 0xDC00 || lo > 0xDFFF) return INVALID;
            i += 6;
            cp = 0x10000 + ((cu - 0xD800) << 10) + (lo - 0xDC00);
        } else if (cu >= 0xDC00 && cu <= 0xDFFF) {
            return INVALID;
        } else {
            cp = cu;
        }
        // Emit UTF-8.
        if (cp < 0x80) {
            out[o++] = (uint8_t)cp;
        } else if (cp < 0x800) {
            out[o++] = (uint8_t)(0xC0 | (cp >> 6));
            out[o++] = (uint8_t)(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out[o++] = (uint8_t)(0xE0 | (cp >> 12));
            out[o++] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F));
            out[o++] = (uint8_t)(0x80 | (cp & 0x3F));
        } else {
            out[o++] = (uint8_t)(0xF0 | (cp >> 18));
            out[o++] = (uint8_t)(0x80 | ((cp >> 12) & 0x3F));
            out[o++] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F));
            out[o++] = (uint8_t)(0x80 | (cp & 0x3F));
        }
    }
    return o;
}
