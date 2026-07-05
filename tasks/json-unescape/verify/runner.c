// runner.c — cost-measurement driver for json-unescape.
// Reads the corpus (len-prefixed records), calls json_unescape on each.
// Run under callgrind; the grader extracts instructions attributed to
// json_unescape and callees via --toggle-collect.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef RUNNER_GIVEN
size_t given_json_unescape(const uint8_t *in, size_t in_len, uint8_t *out);
#define json_unescape given_json_unescape
#else
size_t json_unescape(const uint8_t *in, size_t in_len, uint8_t *out);
#endif

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: runner CORPUS\n");
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("corpus"); return 2; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc((size_t)sz);
    if (fread(data, 1, (size_t)sz, f) != (size_t)sz) { perror("read"); return 2; }
    fclose(f);

    uint8_t *out = malloc(3u * 1u * (1 << 20) + 64); // >= 3*maxrec+4
    unsigned long long checksum = 0, total_in = 0, n_rec = 0;

    // Warmup pass (not measured; callgrind collection toggles on json_unescape,
    // but the first pass also faults in pages so counts are pure).
    // Measured work: one pass over all records.
    size_t off = 0;
    while (off + 4 <= (size_t)sz) {
        uint32_t len;
        memcpy(&len, data + off, 4);
        off += 4;
        if (off + len > (size_t)sz) { fprintf(stderr, "corrupt corpus\n"); return 2; }
        size_t r = json_unescape(data + off, len, out);
        if (r == (size_t)-1) {
            fprintf(stderr, "BUG: corpus record rejected (record %llu)\n", n_rec);
            return 3;
        }
        // fold output into checksum so the call cannot be optimized away
        for (size_t k = 0; k < r; k += 64) checksum += out[k];
        checksum += r;
        total_in += len;
        n_rec++;
        off += len;
    }
    printf("runner: %llu records, %llu input bytes, checksum %llu\n",
           n_rec, total_in, checksum);
    return 0;
}
