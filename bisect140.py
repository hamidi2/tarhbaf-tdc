#!/usr/bin/env python3
"""Bisect the #140 trigger: build hybrid images (user's file with swapped
regions from my passing file), run PC-CONV Read Floppy on each, report."""
import os, shutil, subprocess, sys, time

sys.path.insert(0, '/home/hamidi/code/knit')
from karlmayer_tdc import BLOCK, COPYRIGHT_SIG, parse_catalog, file_blocks, parse_params

DOS = '/home/hamidi/code/knit/dosrun'
USER = '/home/hamidi/dl/td/359hp.img'
MINE = '/tmp/359hp_ours.img'

def key(k, d=0.4):
    subprocess.run(['xdotool', 'key', k], check=False)
    time.sleep(d)

def read_test(tag):
    shutil.copy(tag, f'{DOS}/floppy.img')
    subprocess.run(['pkill', '-9', '-x', 'dosbox-x'], check=False)
    time.sleep(1)
    for f in ('JACQ1.TIF', 'JACQ2.TIF', 'READ.DEF'):
        try: os.remove(f'{DOS}/{f}')
        except OSError: pass
    lg = open('/tmp/bisect-dosbox.log', 'a')
    subprocess.Popen(['dosbox-x', '-conf', f'{DOS}/dosbox-x.conf'],
                     stdout=lg, stderr=subprocess.STDOUT,
                     env={**os.environ, 'DISPLAY': ':99'}, start_new_session=True)
    time.sleep(10)
    out = subprocess.run(['xdotool', 'search', '--name', 'PC-CONV'],
                         capture_output=True, text=True)
    wids = out.stdout.split()
    if wids:
        subprocess.run(['xdotool', 'windowfocus', wids[-1]], check=False)
    time.sleep(0.5)
    key('Return', 2); key('r', 2); key('Return', 2); key('Return', 2)
    ok = False; err = None
    for _ in range(40):
        time.sleep(2)
        if os.path.exists(f'{DOS}/JACQ1.TIF'):
            ok = True
            break
        # detect error dialog: red box present in screenshot
        out = subprocess.run(['xdotool', 'search', '--name', 'PC-CONV'],
                             capture_output=True, text=True)
        wids = out.stdout.split()
        if wids:
            subprocess.run(['xwd', '-id', wids[-1], '-silent', '-out', '/tmp/bi.xwd'])
            data = open('/tmp/bi.xwd', 'rb').read()
            hdr = struct.unpack('>25I', data[:100]) if len(data) > 100 else None
            if hdr:
                w, h, bpp, bpl = hdr[4], hdr[5], hdr[11], hdr[12]
                off = hdr[0] + hdr[19]*12
                raw = b''.join(data[off+y*bpl: off+y*bpl+w*(bpp//8)] for y in range(h))
                from PIL import Image
                img = Image.frombytes('RGB', (w, h), raw, 'raw',
                                      'BGRX' if bpp == 32 else 'BGR')
                px = img.load()
                red = sum(1 for y in range(0, h, 3) for x in range(0, w, 3)
                          if px[x, y][0] > 170 and px[x, y][1] < 90 and px[x, y][2] < 90)
                if red > 200:
                    # grab the error text via OCR-free: screenshot saved for log
                    img.save(f'/tmp/bisect-err-{os.path.basename(tag)}.png')
                    err = 'error-dialog'
                    break
    subprocess.run(['pkill', '-9', '-x', 'dosbox-x'], check=False)
    time.sleep(1)
    return 'PASS' if ok else (err or 'unknown')

import struct  # noqa
u = bytearray(open(USER, 'rb').read())
m = bytearray(open(MINE, 'rb').read())

# region boundaries (disk offsets)
HDR_PARAM = (4096, 4096+180)        # ascii header + 0x00 + param(90)
BITMAP    = (4096+180, 4096+180+192*202)
CATALOG   = (0, 2*BLOCK)

tests = {
    'baseline-mine':    open(MINE,'rb').read(),
    'baseline-user':    open(USER,'rb').read(),
    'user+my-header':   None,   # user file, header/param from mine
    'user+my-bitmap':   None,   # user file, bitmap from mine
    'user+my-catalog':  None,   # user file, catalog from mine
}
v = bytearray(u); v[HDR_PARAM[0]:HDR_PARAM[1]] = m[HDR_PARAM[0]:HDR_PARAM[1]]
tests['user+my-header'] = bytes(v)
v = bytearray(u); v[BITMAP[0]:BITMAP[1]] = m[BITMAP[0]:BITMAP[1]]
tests['user+my-bitmap'] = bytes(v)
v = bytearray(u); v[CATALOG[0]:CATALOG[1]] = m[CATALOG[0]:CATALOG[1]]
tests['user+my-catalog'] = bytes(v)

only = sys.argv[1:] or list(tests)
for name in only:
    if name.startswith('t_'):
        path = f'/tmp/{name}.img'
    else:
        path = f'/tmp/bisect_{name}.img'
        open(path, 'wb').write(tests[name])
    r = read_test(path)
    print(f"{name:18} -> {r}", flush=True)
print("bisect done")
