// reference.c — the oracle for json-unescape.
// Deliberately simple and obviously correct. This defines the semantics.
// NOT the given implementation; used only by the verifier.
#include <stdint.h>
#include <stddef.h>

#define INVALID ((size_t)-1)

static int hex_val(uint8_t c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// Parse \uXXXX starting at in[i] where in[i-1] == '\\' and in[i] == 'u'.
// Returns code unit in *cu and consumed count (5) or -1.
static int parse_u(const uint8_t *in, size_t in_len, size_t i, unsigned *cu) {
    if (i + 5 > in_len) return -1;
    unsigned v = 0;
    for (int k = 1; k <= 4; k++) {
        int h = hex_val(in[i + k]);
        if (h < 0) return -1;
        v = (v << 4) | (unsigned)h;
    }
    *cu = v;
    return 5;
}

static size_t emit_utf8(unsigned cp, uint8_t *out) {
    if (cp < 0x80) {
        out[0] = (uint8_t)cp;
        return 1;
    } else if (cp < 0x800) {
        out[0] = (uint8_t)(0xC0 | (cp >> 6));
        out[1] = (uint8_t)(0x80 | (cp & 0x3F));
        return 2;
    } else if (cp < 0x10000) {
        out[0] = (uint8_t)(0xE0 | (cp >> 12));
        out[1] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (uint8_t)(0x80 | (cp & 0x3F));
        return 3;
    } else {
        out[0] = (uint8_t)(0xF0 | (cp >> 18));
        out[1] = (uint8_t)(0x80 | ((cp >> 12) & 0x3F));
        out[2] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F));
        out[3] = (uint8_t)(0x80 | (cp & 0x3F));
        return 4;
    }
}

size_t ref_json_unescape(const uint8_t *in, size_t in_len, uint8_t *out) {
    size_t i = 0, o = 0;
    while (i < in_len) {
        uint8_t c = in[i];
        if (c <= 0x1F || c == '"') return INVALID;
        if (c != '\\') {
            out[o++] = c;
            i++;
            continue;
        }
        // escape
        if (i + 1 >= in_len) return INVALID;
        uint8_t e = in[i + 1];
        switch (e) {
            case '"':  out[o++] = '"';  i += 2; break;
            case '\\': out[o++] = '\\'; i += 2; break;
            case '/':  out[o++] = '/';  i += 2; break;
            case 'b':  out[o++] = '\b'; i += 2; break;
            case 'f':  out[o++] = '\f'; i += 2; break;
            case 'n':  out[o++] = '\n'; i += 2; break;
            case 'r':  out[o++] = '\r'; i += 2; break;
            case 't':  out[o++] = '\t'; i += 2; break;
            case 'u': {
                unsigned cu;
                if (parse_u(in, in_len, i + 1, &cu) < 0) return INVALID;
                i += 6;
                if (cu >= 0xD800 && cu <= 0xDBFF) {
                    // need low surrogate: \uDC00-\uDFFF immediately
                    if (i + 1 >= in_len || in[i] != '\\' || in[i + 1] != 'u')
                        return INVALID;
                    unsigned lo;
                    if (parse_u(in, in_len, i + 1, &lo) < 0) return INVALID;
                    if (lo < 0xDC00 || lo > 0xDFFF) return INVALID;
                    i += 6;
                    unsigned cp = 0x10000 + ((cu - 0xD800) << 10) + (lo - 0xDC00);
                    o += emit_utf8(cp, out + o);
                } else if (cu >= 0xDC00 && cu <= 0xDFFF) {
                    return INVALID; // lone low surrogate
                } else {
                    o += emit_utf8(cu, out + o);
                }
                break;
            }
            default:
                return INVALID;
        }
    }
    return o;
}
