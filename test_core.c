/* test_core.c — native byte-exact validation of tdc_format.c against samples.
 * Usage: test_core <original.img> <rows.bin> <width_bits> <height> <width_px> */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tdc_format.h"

static uint8_t orig[TDC_DISK_SIZE], out[TDC_DISK_SIZE];

static uint8_t *read_file(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    uint8_t *buf;
    long n;
    if (!f) { perror(path); exit(2); }
    fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
    buf = malloc(n);
    if (fread(buf, 1, n, f) != (size_t)n) { fprintf(stderr, "short read\n"); exit(2); }
    fclose(f);
    *len = n;
    return buf;
}

int main(int argc, char **argv)
{
    size_t rows_len;
    uint8_t *rows;
    tdc_template tpl;
    int W, H, Wpx, i, diffs, rc;

    if (argc != 6) { fprintf(stderr, "usage: %s img rows wbits h wpx\n", argv[0]); return 2; }
    { size_t n; uint8_t *d = read_file(argv[1], &n);
      if (n != TDC_DISK_SIZE) { fprintf(stderr, "bad img size\n"); return 2; }
      memcpy(orig, d, TDC_DISK_SIZE); free(d); }
    rows = read_file(argv[2], &rows_len);
    W = atoi(argv[3]); H = atoi(argv[4]); Wpx = atoi(argv[5]);

    rc = tdc_parse_template(orig, &tpl);
    if (rc) { fprintf(stderr, "parse_template failed: %d\n", rc); return 1; }
    if (tpl.width_bits != W || tpl.height != H || tpl.width_px != Wpx) {
        fprintf(stderr, "geom mismatch: disk %d/%d/%d vs args %d/%d/%d\n",
                tpl.width_bits, tpl.height, tpl.width_px, W, H, Wpx);
        return 1;
    }
    if ((int)rows_len != H * (W / 8)) { fprintf(stderr, "rows size mismatch\n"); return 1; }

    printf("template: name='%s' date='%s' wbits=%d wpx=%d h=%d trailer=%d\n",
           tpl.name, tpl.date, tpl.width_bits, tpl.width_px, tpl.height,
           tpl.trailer_len);

    rc = tdc_build_disk(&tpl, rows, H, 1, 1, H, 0, 0, out);
    if (rc) { fprintf(stderr, "build_disk failed: %d\n", rc); return 1; }

    diffs = 0;
    for (i = 0; i < TDC_DISK_SIZE; i++)
        if (orig[i] != out[i]) {
            if (diffs < 10) fprintf(stderr, "  diff @%d: %02x vs %02x\n", i, orig[i], out[i]);
            diffs++;
        }
    printf("diffs: %d -> %s\n", diffs, diffs == 0 ? "BYTE-EXACT PASS" : "FAIL");
    return diffs == 0 ? 0 : 1;
}
