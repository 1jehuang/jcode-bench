// runner.c — cost driver for float-print. Reads uint32 bit patterns,
// calls float_print on each. Run under callgrind with --toggle-collect.
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef RUNNER_GIVEN
size_t given_float_print(float f, char *out);
#define float_print given_float_print
#else
size_t float_print(float f, char *out);
#endif

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: runner CORPUS\n"); return 2; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("corpus"); return 2; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint32_t *bits = malloc((size_t)sz);
    if (fread(bits, 1, (size_t)sz, f) != (size_t)sz) { perror("read"); return 2; }
    fclose(f);
    size_t n = (size_t)sz / 4;
    char out[40];
    unsigned long long checksum = 0;
    for (size_t i = 0; i < n; i++) {
        float v;
        memcpy(&v, &bits[i], 4);
        size_t r = float_print(v, out);
        checksum += r + (unsigned char)out[0];
    }
    printf("runner: %zu floats, checksum %llu\n", n, checksum);
    return 0;
}
