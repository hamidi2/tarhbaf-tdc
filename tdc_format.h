/* tdc_format.h — Karl Mayer TDC jacquard floppy: portable reader/writer core.
 * See FORMAT.md. Byte-exact vs samples (test_core). */
#ifndef TDC_FORMAT_H
#define TDC_FORMAT_H

#include <stdint.h>

#define TDC_BLOCK       2048
#define TDC_DISK_SIZE   1474560
#define TDC_TRAILER_MAX 1868
#define TDC_NAME_MAX    14
#define TDC_DATA_BLOCK_FIRST 2
#define TDC_DATA_BLOCK_LAST  2878   /* last block reserved for LAENGE */

typedef struct {
    uint8_t  param[90];                /* machine config: param block minus dynamic fields ([88..89] checksum rebuilt) */
    uint8_t  trailer[TDC_TRAILER_MAX]; /* machine config: copyright block (constant prefix; cut at block end) */
    int      trailer_len;
    uint8_t  laenge[TDC_BLOCK];        /* optional: real LAENGE from a reference
                                          floppy of the SAME article; if
                                          laenge_len==0 the pure generator
                                          (tdc_gen_laenge) is used instead */
    int      laenge_len;
    int      width_bits;               /* packed design width in bits (mult. of 8) */
    int      width_px;                 /* real design width in pixels */
    int      height;                   /* total design rows */
    char     name[TDC_NAME_MAX];       /* design name for ASCII header */
    char     date[16];                 /* dd.mm.yy */
} tdc_template;

/* Extract machine-config pieces + geometry from an existing disk image. 0 = ok. */
int tdc_parse_template(const uint8_t *disk, tdc_template *tpl);

/* Generate the LAENGE.FAC block purely from (w, h) — proven against PC-CONV
 * (acceptance test 2026-10-26, exp/laenge_model.py). Returns content length. */
int tdc_gen_laenge(int w_bits, int h_rows, uint8_t *out /* TDC_BLOCK bytes */);

/* Max rows one disk can hold for this template's geometry. */
int tdc_rows_capacity(const tdc_template *tpl);

/* How many disks a design of `rows` needs (1 or 2). */
int tdc_disk_count(const tdc_template *tpl, int rows);

/* Build one floppy image.
 * rows: design-domain packed rows (MSB first, width_bits/8 bytes each,
 *       pad bits must be 1), TOP-first order, this disk's slice only.
 * thisdisk: 1 or 2. disk1_rows/disk2_start(1-based from bottom)/disk2_rows:
 *       global multi-disk info written into the param block.
 * Returns 0 on success. */
int tdc_build_disk(const tdc_template *tpl, const uint8_t *rows, int nrows,
                   int ndisks, int thisdisk,
                   int disk1_rows, int disk2_start, int disk2_rows,
                   uint8_t *out);

#endif
