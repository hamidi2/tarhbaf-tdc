#!/usr/bin/env python3
"""Robustly drive PC-CONV: dismiss license, Write Floppy, wait for completion."""
import os, subprocess, sys, time, struct
from PIL import Image

WID = sys.argv[1]

def key(k, d=0.5):
    subprocess.run(['xdotool', 'key', k], check=False)
    time.sleep(d)

def shot(path='/tmp/step.png'):
    subprocess.run(['xwd', '-id', WID, '-silent', '-out', '/tmp/step.xwd'], check=False)
    data = open('/tmp/step.xwd', 'rb').read()
    hdr = struct.unpack('>25I', data[:100])
    w, h, bpp, bpl = hdr[4], hdr[5], hdr[11], hdr[12]
    off = hdr[0] + hdr[19]*12
    raw = b''.join(data[off+y*bpl: off+y*bpl+w*(bpp//8)] for y in range(h))
    img = Image.frombytes('RGB', (w, h), raw, 'raw', 'BGRX' if bpp == 32 else 'BGR')
    img.save(path)
    return img

# 1. license
key('Return', 3)
img = shot('/tmp/s1.png')

# 2. write floppy dialog
key('w', 4)
img = shot('/tmp/s2.png')

# 3. confirm (135HQ.DEF preselected)
key('Return', 8)
img = shot('/tmp/s3.png')
px = img.load()
w, h = img.size
# wait until the write finishes: look for the red progress/error box disappearing
# simpler: poll floppy mtime for 60s until unchanged for 5s
path = os.path.expanduser('~/code/knit/dosrun/floppy.img')
last = -1
stable = 0
for _ in range(60):
    try:
        m = os.path.getmtime(path)
    except OSError:
        m = -1
    if m == last:
        stable += 1
        if stable >= 5 and last > 0:
            break
    else:
        stable = 0
        last = m
    time.sleep(2)
shot('/tmp/s4.png')
print('done; floppy mtime', last)
