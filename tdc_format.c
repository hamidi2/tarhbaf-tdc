/* tdc_format.c — Karl Mayer TDC jacquard floppy: portable core. See FORMAT.md. */
#include "tdc_format.h"
#include <stdlib.h>
#include <string.h>

#define BE16(p)  ((int)((p)[0] << 8) | (p)[1])
#define LE16(p)  ((int)((p)[0]) | ((int)(p)[1] << 8))

static const uint8_t SIG_COPYRIGHT[] = "Copyright (C) KARL MAYER";
#define SIG_LEN 24

static int name_ok(const uint8_t *rec)
{
    int i;
    if (rec[0] != 0) return 0;
    for (i = 1; i < 12; i++) {
        uint8_t c = rec[i];
        if (c != ' ' && (c < '0' || c > '9') && (c < 'A' || c > 'Z'))
            return 0;
    }
    return 1;
}

/* Collect file blocks of `want` ("MUSTER" or "LAENGE") from the directory.
 * Returns block count, fills blocks[]. */
static int catalog_blocks(const uint8_t *disk, const char *want,
                          int *blocks, int max)
{
    int off = 0, n = 0;
    while (off + 32 <= 2 * TDC_BLOCK && n < max) {
        const uint8_t *rec = disk + off;
        char name[13];
        int cnt, i;
        if (!name_ok(rec)) break;
        memcpy(name, rec + 1, 11); name[11] = 0;
        cnt = rec[15] / 0x10;
        if (strncmp(name, want, 6) == 0) {
            for (i = 0; i < cnt; i++)
                blocks[n++] = LE16(rec + 16 + 2 * i);
        }
        off += 32;
    }
    return n;
}

static void field(char *dst, int dstsz, const char *line)
{
    /* value after the last ':' up to end, trimmed */
    const char *c = strrchr(line, ':');
    int n = 0;
    if (c) c++;
    else c = line;
    while (*c == ' ') c++;
    while (c[n] && c[n] != ' ' && n < dstsz - 1) { dst[n] = c[n]; n++; }
    dst[n] = 0;
}

int tdc_parse_template(const uint8_t *disk, tdc_template *tpl)
{
    int mb[2900], lb[4];
    int nmb, nlb, i;
    uint8_t *data;
    int total;
    const uint8_t *sig;
    int hdr_len, base, content_end, inblk, tr_len;
    const uint8_t *lblk;

    memset(tpl, 0, sizeof *tpl);
    nmb = catalog_blocks(disk, "MUSTER", mb, 2900);
    nlb = catalog_blocks(disk, "LAENGE", lb, 4);
    if (nmb <= 0 || nlb <= 0) return -1;

    total = nmb * TDC_BLOCK;
    data = (uint8_t *)malloc(total);
    if (!data) return -2;
    for (i = 0; i < nmb; i++)
        memcpy(data + (size_t)i * TDC_BLOCK, disk + (size_t)mb[i] * TDC_BLOCK,
               TDC_BLOCK);

    /* ASCII header ends with "\r\n\x00" */
    sig = NULL;
    for (i = 0; i < 400; i++)
        if (data[i] == '\r' && data[i+1] == '\n' && data[i+2] == 0) { sig = data + i; break; }
    if (!sig) { free(data); return -3; }
    hdr_len = (int)(sig - data) + 2;          /* including final \r\n */

    {
        char line1[64] = {0}, line2[64] = {0}, line3[64] = {0};
        const char *p = (const char *)data, *q;
        q = strchr(p, '\r');            if (!q || q - p > 60) { free(data); return -3; }
        memcpy(line1, p, q - p); p = q + 2;
        q = strchr(p, '\r');            if (!q || q - p > 60) { free(data); return -3; }
        memcpy(line2, p, q - p); p = q + 2;
        q = strchr(p, '\r');            if (!q || q - p > 60) { free(data); return -3; }
        memcpy(line3, p, q - p);
        field(tpl->name, TDC_NAME_MAX, line2);
        field(tpl->date, sizeof tpl->date, line3);
        (void)line1;
    }

    base = hdr_len + 1;                        /* + the 0x00 byte */
    if (base + 90 > total) { free(data); return -3; }
    memcpy(tpl->param, data + base, 90);
    tpl->width_bits = BE16(tpl->param + 8);
    tpl->width_px   = BE16(tpl->param + 62);
    tpl->height     = BE16(tpl->param + 10);

    {
        int dbytes = tpl->width_bits / 8;
        int pitch  = (dbytes + 1) / 2 * 2 + 2;
        content_end = base + 90 + BE16(tpl->param + 14) * pitch;
    }
    if (content_end > total) { free(data); return -4; }
    inblk = content_end % TDC_BLOCK;
    tr_len = TDC_TRAILER_MAX;
    if (tr_len > TDC_BLOCK - inblk) tr_len = TDC_BLOCK - inblk;
    if (memcmp(data + content_end, SIG_COPYRIGHT, SIG_LEN) != 0) { free(data); return -5; }
    memcpy(tpl->trailer, data + content_end, tr_len);
    tpl->trailer_len = tr_len;

    lblk = disk + (size_t)lb[0] * TDC_BLOCK;
    sig = NULL;
    for (i = 0; i + SIG_LEN <= TDC_BLOCK; i++)
        if (memcmp(lblk + i, SIG_COPYRIGHT, SIG_LEN) == 0) { sig = lblk + i; break; }
    if (!sig) { free(data); return -6; }
    /* optional real LAENGE (same-article reference); generator is the default */
    tpl->laenge_len = (int)(sig - lblk);
    if (tpl->laenge_len > TDC_BLOCK) tpl->laenge_len = TDC_BLOCK;
    memcpy(tpl->laenge, lblk, tpl->laenge_len);

    free(data);
    return 0;
}

/* ---- LAENGE generator (fully reverse-engineered; see exp/laenge_model.py).
 * Accepted byte-exact-equivalent by PC-CONV Read Floppy (acceptance 2026-10-26). */
int tdc_gen_laenge(int w_bits, int h_rows, uint8_t *out)
{
    int wpb = (w_bits + 7) / 8;          /* real row bytes */
    int rb = wpb + (wpb % 2);            /* padded to even (storage row bytes) */
    int pitch = rb + 2;
    int L = (180 + h_rows * ((rb % 64) + 2)) % 2048;
    int S = (640 + pitch * h_rows) / 256;
    uint8_t sep[3];
    int sep_len;
    int blobend, ph, s0, s, i, zb;

    if (rb == wpb) {                     /* no pad byte: 2-byte marker */
        sep[0] = (uint8_t)(rb - 1);
        sep[1] = (uint8_t)(256 - rb);
        sep_len = 2;
    } else {                             /* padded width: 3-byte marker */
        sep[0] = 0;
        sep[1] = (uint8_t)(wpb - 1);
        sep[2] = (uint8_t)(256 - wpb);
        sep_len = 3;
    }

    memset(out, 0, TDC_BLOCK);
    out[0] = (uint8_t)(S >> 8);
    out[1] = (uint8_t)(L & 0xFF);
    out[2] = (uint8_t)(S & 0xFF);

    /* descriptor blob (machine-constant prefix; last 4 bytes not validated) */
    zb = L - 1556;
    blobend = 3;
    if (zb >= 3 && zb + 20 <= L - 3) {
        static const uint8_t blob[16] =
            { 0x04, 0x00, 0x00, 0x02, 0x0e, 0x6e, 0x78, 0x6e,
              0x61, 0x6c, 0x18, 0x12, 0x00, 0x00, 0x00, 0x00 };
        memcpy(out + zb, blob, 16);
        blobend = zb + 20;
    }

    /* marker grid anchored to tail (last marker at L-len(sep)); FF elsewhere */
    ph = (L - sep_len) % pitch;
    s0 = ph;
    while (s0 < blobend) s0 += pitch;
    for (i = blobend; i < L; i++)
        if (out[i] == 0) out[i] = 0xFF;
    for (s = s0; s + sep_len <= L; s += pitch)
        memcpy(out + s, sep, sep_len);
    return L;
}

int tdc_rows_capacity(const tdc_template *tpl)
{
    int dbytes = tpl->width_bits / 8;
    int pitch  = (dbytes + 1) / 2 * 2 + 2;
    int avail  = (TDC_DATA_BLOCK_LAST - TDC_DATA_BLOCK_FIRST) * TDC_BLOCK
                 - 180 - tpl->trailer_len - TDC_BLOCK /* LAENGE block */;
    if (avail < 0) avail = 0;
    return avail / pitch;
}

int tdc_disk_count(const tdc_template *tpl, int rows)
{
    int cap = tdc_rows_capacity(tpl);
    return rows <= cap ? 1 : 2;   /* 2 disks hold far more than any design so far */
}

static void put_be16(uint8_t *p, int v)  { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
static void put_le16(uint8_t *p, int v)  { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }

static int put_cat_rec(uint8_t *p, const char *name, int seq, int grp,
                       const int *blocks, int nblk)
{
    int i;
    memset(p, 0xE5, 32);
    p[0] = 0;
    memcpy(p + 1, name, 11);
    p[12] = (uint8_t)seq; p[13] = 0; p[14] = (uint8_t)grp;
    p[15] = (uint8_t)(0x10 * nblk);
    for (i = 0; i < nblk; i++) put_le16(p + 16 + 2 * i, blocks[i]);
    return 32;
}

static void make_ascii_header(uint8_t *out, const char *name, const char *date)
{
    int i, n;
    uint8_t *w = out;
    memcpy(w, "MASCHINENTYP :", 14); w += 14;
    memcpy(w, "JACQUARD", 8); w += 8;
    for (i = 0; i < 5; i++) *w++ = ' ';
    memcpy(w, "\r\n", 2); w += 2;
    memcpy(w, "Muster...... : ", 15); w += 15;
    n = (int)strlen(name); if (n > 13) n = 13;
    memcpy(w, name, n); w += n;
    for (i = n; i < 13; i++) *w++ = ' ';
    memcpy(w, "\r\n", 2); w += 2;
    memcpy(w, "Datum....... : ", 15); w += 15;
    n = (int)strlen(date); if (n > 13) n = 13;
    memcpy(w, date, n); w += n;
    for (i = n; i < 13; i++) *w++ = ' ';
    memcpy(w, "\r\n\x00", 3); w += 3;
    (void)w;
}

int tdc_build_disk(const tdc_template *tpl, const uint8_t *rows, int nrows,
                   int ndisks, int thisdisk,
                   int disk1_rows, int disk2_start, int disk2_rows,
                   uint8_t *out)
{
    int dbytes = tpl->width_bits / 8;
    int pitch  = (dbytes + 1) / 2 * 2 + 2;
    uint8_t hdr[90];
    uint8_t par[90];
    uint8_t *body;
    int body_len, cap, pos, i, nblocks, laenge_block, cat_len, chk;
    int r, seq, grp, blk, left;
    const char *cname = "MUSTER  FAC";

    memset(out, 0xE5, TDC_DISK_SIZE);
    memcpy(par, tpl->param, 88);
    par[2] = (uint8_t)ndisks;
    par[3] = (uint8_t)thisdisk;
    put_be16(par + 8,  tpl->width_bits);
    put_be16(par + 10, tpl->height);
    if (thisdisk == 2) put_be16(par + 12, disk2_start);
    else { par[12] = 0; par[13] = 1; }
    put_be16(par + 14, nrows);
    put_le16(par + 21, pitch);
    put_be16(par + 24, disk1_rows);
    put_be16(par + 26, disk2_start);
    put_be16(par + 28, disk2_rows);
    put_be16(par + 42, tpl->height);
    put_be16(par + 62, tpl->width_px);
    /* byte 87 fingerprint: 3*(ord(name[2]) + (day-1)%10 - 26) — از باتری‌های
       PC-CONV/DOSBox (exp/battery_*.sh)؛ نام‌های ≤2 حرف/کوچک همان مقادیر
       fallback را می‌دهند، پس مستقیم از نام واقعی محاسبه می‌کنیم */
    if (strlen(tpl->name) >= 3) {
        int day = atoi(tpl->date);              /* dd.mm.yy */
        par[87] = (uint8_t)((3 * ((uint8_t)tpl->name[2] + (day > 0 ? (day - 1) % 10 : 0) - 26)) & 0xFF);
    }

    make_ascii_header(hdr, tpl->name, tpl->date);
    chk = 0;
    for (i = 0; i < 90; i++) chk += hdr[i];
    for (i = 0; i < 88; i++) chk += par[i];
    put_be16(par + 88, chk & 0xFFFF);

    body_len = 180 + nrows * pitch;
    cap = (TDC_DATA_BLOCK_LAST - TDC_DATA_BLOCK_FIRST) * TDC_BLOCK;
    if (body_len + tpl->trailer_len > cap) return -10;
    body = (uint8_t *)malloc(body_len);
    if (!body) return -2;
    memcpy(body, hdr, 90);
    memcpy(body + 90, par, 90);
    for (r = 0; r < nrows; r++) {                 /* bottom row first */
        const uint8_t *src = rows + (size_t)(nrows - 1 - r) * dbytes;
        uint8_t *dst = body + 180 + (size_t)r * pitch;
        unsigned sum = 0;
        for (i = 0; i < dbytes; i++) { dst[i] = (uint8_t)(src[i] ^ 0xFF); sum += dst[i]; }
        if (dbytes % 2) { dst[dbytes] = 0; sum += 0; }
        put_be16(dst + dbytes + (dbytes % 2), sum & 0xFFFF);
    }

    nblocks = (body_len + TDC_BLOCK - 1) / TDC_BLOCK;
    laenge_block = TDC_DATA_BLOCK_FIRST + nblocks;
    /* directory */
    pos = 0; seq = 0; grp = 0; blk = TDC_DATA_BLOCK_FIRST; left = nblocks;
    while (left > 0) {
        int take = left < 8 ? left : 8;
        pos += put_cat_rec(out + pos, cname, seq, grp, NULL, 0);
        /* fill blocks now (rec already placed; simpler: build then place) */
        pos -= 32;
        {
            int bl[8];
            for (i = 0; i < take; i++) bl[i] = blk + i;
            pos += put_cat_rec(out + pos, cname, seq, grp, bl, take);
        }
        blk += take; left -= take;
        if (++seq == 32) { seq = 0; grp++; }
    }
    {
        int lbl[1]; lbl[0] = laenge_block;
        pos += put_cat_rec(out + pos, "LAENGE  FAC", 0, 0, lbl, 1);
    }
    cat_len = pos;

    memcpy(out + TDC_DATA_BLOCK_FIRST * TDC_BLOCK, body, body_len);
    pos = TDC_DATA_BLOCK_FIRST * TDC_BLOCK + body_len;
    {
        int room = ((pos / TDC_BLOCK) + 1) * TDC_BLOCK - pos;
        int n = tpl->trailer_len < room ? tpl->trailer_len : room;
        memcpy(out + pos, tpl->trailer, n);
    }
    pos = laenge_block * TDC_BLOCK;
    if (tpl->laenge_len > 0) {
        /* real LAENGE from a same-article reference floppy: byte-exact path */
        memcpy(out + pos, tpl->laenge, tpl->laenge_len);
        pos += tpl->laenge_len;
    } else {
        /* pure generator: accepted by PC-CONV (acceptance test 2026-10-26) */
        uint8_t *la = (uint8_t *)malloc(TDC_BLOCK);
        int la_len;
        if (!la) { free(body); return -2; }
        la_len = tdc_gen_laenge(tpl->width_bits, tpl->height, la);
        memcpy(out + pos, la, la_len);
        pos += la_len;
        free(la);
    }
    {
        int room = ((pos / TDC_BLOCK) + 1) * TDC_BLOCK - pos;
        int n = tpl->trailer_len < room ? tpl->trailer_len : room;
        memcpy(out + pos, tpl->trailer, n);
    }
    free(body);
    (void)cat_len;
    return 0;
}
