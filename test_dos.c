/* test_dos.c — build 135hq with the DOS-machine template pieces (white
 * experiment) and compare with the actual PC-CONV-written floppy. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tdc_format.h"

static uint8_t dos[TDC_DISK_SIZE], out[TDC_DISK_SIZE];
static uint8_t rows[256 * 206];   /* 1648/8 = 206 bytes per design row */

int main(void)
{
    tdc_template tpl;
    FILE *f;
    memset(&tpl, 0, sizeof tpl);
    f = fopen("testdata/emb_param88.bin", "rb");
    if (!f || fread(tpl.param, 1, 88, f) != 88) return 2;
    fclose(f);
    f = fopen("testdata/emb_laenge.bin", "rb");
    if (!f) return 2;
    tpl.laenge_len = fread(tpl.laenge, 1, TDC_BLOCK, f);
    fclose(f);
    f = fopen("testdata/emb_trailer.bin", "rb");
    if (!f) return 2;
    tpl.trailer_len = fread(tpl.trailer, 1, TDC_TRAILER_MAX, f);
    fclose(f);
    tpl.width_bits = 1648; tpl.width_px = 1648; tpl.height = 256;
    strcpy(tpl.name, "135HQ");
    strcpy(tpl.date, "19.10.26");

    f = fopen("testdata/135hq_dos.img", "rb");
    if (!f || fread(dos, 1, TDC_DISK_SIZE, f) != TDC_DISK_SIZE) return 2;
    fclose(f);
    f = fopen("testdata/135hq.rows", "rb");
    if (!f || fread(rows, 1, sizeof rows, f) != sizeof rows) return 2;
    fclose(f);

    int rc = tdc_build_disk(&tpl, rows, 256, 1, 1, 256, 0, 0, out);
    if (rc) { printf("build rc=%d\n", rc); return 1; }
    int diffs = 0;
    for (int i = 0; i < TDC_DISK_SIZE; i++)
        if (dos[i] != out[i]) diffs++;
    printf("diffs vs PC-CONV-written floppy: %d -> %s\n", diffs,
           diffs == 0 ? "BYTE-EXACT PASS" : "FAIL");
    return diffs == 0 ? 0 : 1;
}
