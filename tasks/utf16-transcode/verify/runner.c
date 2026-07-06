// runner.c — cost driver for utf16-transcode. Corpus: u32 count then u16 units
// per record. Run under callgrind with --toggle-collect.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef RUNNER_GIVEN
size_t given_utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out);
#define utf16_to_utf8 given_utf16_to_utf8
#else
size_t utf16_to_utf8(const uint16_t *in, size_t n, uint8_t *out);
#endif

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: runner CORPUS\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("corpus"); return 2; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc((size_t)sz);
    if (fread(data, 1, (size_t)sz, f) != (size_t)sz) { perror("read"); return 2; }
    fclose(f);
    uint8_t *out = malloc(3u * (1u << 21) + 64);
    unsigned long long checksum = 0, nrec = 0;
    size_t off = 0;
    while (off + 4 <= (size_t)sz) {
        uint32_t cnt; memcpy(&cnt, data + off, 4); off += 4;
        if (off + 2ull * cnt > (size_t)sz) { fprintf(stderr, "corrupt corpus\n"); return 2; }
        size_t r = utf16_to_utf8((const uint16_t *)(data + off), cnt, out);
        if (r == (size_t)-1) { fprintf(stderr, "BUG: corpus record rejected\n"); return 3; }
        for (size_t k = 0; k < r; k += 64) checksum += out[k];
        checksum += r; nrec++;
        off += 2ull * cnt;
    }
    printf("runner: %llu records, checksum %llu\n", nrec, checksum);
    return 0;
}
