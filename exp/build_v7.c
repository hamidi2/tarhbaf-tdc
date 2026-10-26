/* build_v7.c — build a v7-style floppy (generated LAENGE) for acceptance test.
 * usage: build_v7 <ref.img> <rows.bin> <nrows> <wbits> <h> <wpx> <out.img>
 * template param+trailer from ref.img; laenge_len=0 → pure generator. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tdc_format.h"

static unsigned char disk_buf[TDC_DISK_SIZE];

int main(int argc, char **argv)
{
    tdc_template t;
    FILE *f;
    uint8_t *rows;
    long sz;
    int wbits = atoi(argv[4]), h = atoi(argv[5]), wpx = atoi(argv[6]);
    int nrows = atoi(argv[3]);
    if (argc < 8) { fprintf(stderr, "args\n"); return 2; }
    f = fopen(argv[1], "rb");
    if (!f) { perror("ref"); return 1; }
    if (fread(disk_buf, 1, TDC_DISK_SIZE, f) != TDC_DISK_SIZE) { perror("read"); return 1; }
    fclose(f);
    if (tdc_parse_template(disk_buf, &t) != 0) { fprintf(stderr, "parse\n"); return 1; }
    t.laenge_len = 0;                       /* force pure generator */
    strcpy(t.name, "AAA");
    strcpy(t.date, "26.10.26");
    t.width_bits = wbits; t.width_px = wpx; t.height = h;
    rows = malloc((size_t)nrows * (wbits/8));
    f = fopen(argv[2], "rb");
    if (!f) { perror("rows"); return 1; }
    sz = (long)nrows * (wbits/8);
    if (fread(rows, 1, sz, f) != (size_t)sz) { perror("rows read"); return 1; }
    fclose(f);
    if (tdc_build_disk(&t, rows, nrows, 1, 1, nrows, 0, 0, disk_buf) != 0) {
        fprintf(stderr, "build failed\n"); return 1;
    }
    f = fopen(argv[7], "wb");
    fwrite(disk_buf, 1, TDC_DISK_SIZE, f);
    fclose(f);
    printf("v7 floppy written: %s\n", argv[7]);
    return 0;
}
