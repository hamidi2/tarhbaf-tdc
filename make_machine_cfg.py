#!/usr/bin/env python3
"""make_machine_cfg.py — ساخت machine_cfg.h از یک فلاپی مرجع.
کاربرانِ سیستم لایسنس‌دار Karl Mayer: یک ایمیج خام فلاپی کارکرده (خروجی
Read Floppy یا dd از فلاپی) بدهید؛ ثابت‌های ماشین (پارامتر + تریلر کپی‌رایت)
استخراج و در machine_cfg.h نوشته می‌شود. سپس بیلد کنید تا exe مستقل بگیرید.

usage: python3 make_machine_cfg.py <reference_floppy.img> [out=machine_cfg.h]
"""
import sys, os

BLOCK = 2048
TRAILER_MAX = 1868

def parse_catalog(disk):
    recs, off = [], 0
    while off + 32 <= 2 * BLOCK:
        rec = disk[off:off+32]
        if rec[0] != 0:
            break
        try:
            name = rec[1:12].decode('ascii')
        except UnicodeDecodeError:
            break
        if not name.replace(' ', '').isalnum():
            break
        n = rec[15] // 0x10
        blocks = [int.from_bytes(rec[16+2*i:18+2*i], 'little') for i in range(n)]
        recs.append((name, blocks))
        off += 32
    return recs

def blocks_of(recs, want):
    out = []
    for name, blks in recs:
        if name.startswith(want):
            out += blks
    return out

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    disk = open(sys.argv[1], 'rb').read()
    if len(disk) != 2880 * 512:
        print('خطا: فایل باید ایمیج خام فلاپی ۱٫۴۴ مگابایتی باشد.'); sys.exit(1)
    recs = parse_catalog(disk)
    mb = blocks_of(recs, 'MUSTER')
    lb = blocks_of(recs, 'LAENGE')
    if not mb or not lb:
        print('خطا: این فایل شبیه فلاپی TDC نیست (MUSTER/LAENGE پیدا نشد).'); sys.exit(1)
    data = b''.join(disk[b*BLOCK:(b+1)*BLOCK] for b in mb)
    e = data.find(b'\r\n\x00')
    if not 0 < e < 200:
        print('خطا: هدر MUSTER پیدا نشد.'); sys.exit(1)
    par90 = data[e+3:e+3+90]
    rows = int.from_bytes(par90[14:16], 'big')
    pitch = int.from_bytes(par90[21:23], 'little')
    par = par90[:88]
    content_end = e + 3 + 90 + rows * pitch
    inblk = content_end % BLOCK
    tr_len = min(TRAILER_MAX, BLOCK - inblk)
    trailer = data[content_end:content_end+tr_len]
    if not trailer.startswith(b'Copyright (C) KARL MAYER'):
        print('خطا: تریلر کپی‌رایت کارل مایر سر جایش نیست — فایل خراب است؟'); sys.exit(1)

    out = sys.argv[2] if len(sys.argv) > 2 else 'machine_cfg.h'
    with open(out, 'w') as f:
        f.write('/* machine_cfg.h — تولیدشده توسط make_machine_cfg.py از فلاپی مرجع\n'
                ' * سیستم لایسنس‌دار خودتان. این مقادیر ثابتِ تنظیمات ماشین‌اند،\n'
                ' * نه دادهٔ طرح. این فایل را publish نکنید. */\n')
        f.write('#define MCFG_PARAM88 { '
                + ', '.join(f'0x{b:02x}' for b in par) + ' }\n')
        f.write(f'#define MCFG_TRAILER_LEN {len(trailer)}\n')
        f.write('#define MCFG_TRAILER { '
                + ', '.join(f'0x{b:02x}' for b in trailer) + ' }\n')
    print(f'{out} ساخته شد (param 88B + trailer {len(trailer)}B). حالا بیلد کنید.')

main()
