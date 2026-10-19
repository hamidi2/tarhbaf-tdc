#!/usr/bin/env python3
"""Run PC-CONV experiments in the running dosbox-x: for each TIF, overwrite the
DEF's source, rewrite the floppy, and capture the result image."""
import os, shutil, subprocess, sys, time, struct
from PIL import Image

HOME = os.path.expanduser('~')
DOS = f'{HOME}/code/knit/dosrun'
EXP = f'{HOME}/code/knit/exp'
EMPTY = f'{HOME}/code/knit/samples/formatted_empty_image'
WID = sys.argv[1] if len(sys.argv) > 1 else None

def key(k, delay=0.25):
    subprocess.run(['xdotool', 'key', k], check=False)
    time.sleep(delay)

def shot(path):
    subprocess.run(['xwd', '-id', WID, '-silent', '-out', path], check=False)
    data = open(path, 'rb').read()
    hdr = struct.unpack('>25I', data[:100])
    w, h, bpp, bpl = hdr[4], hdr[5], hdr[11], hdr[12]
    off = hdr[0] + hdr[19]*12
    raw = b''.join(data[off+y*bpl: off+y*bpl+w*(bpp//8)] for y in range(h))
    Image.frombytes('RGB', (w, h), raw, 'raw',
                    'BGRX' if bpp == 32 else 'BGR').save(path.replace('.xwd', '.png'))

def nz(d):
    return sum(1 for b in d if b != 0xe5)

names = sys.argv[2:] or ['white','black','dot00','dotlast','rowtop','rowbottom',
                         'colleft','colright','checker','halftop']
for n in names:
    shutil.copy(f'{EXP}/{n}.tif', f'{DOS}/135HQ.TIF')
    shutil.copy(EMPTY, f'{DOS}/floppy.img')
    key('w'); time.sleep(1.2)
    key('Return'); time.sleep(25)
    d = open(f'{DOS}/floppy.img','rb').read()
    changed = nz(d) > nz(open(EMPTY,'rb').read())
    shot(f'{EXP}/{n}.xwd')
    shutil.copy(f'{DOS}/floppy.img', f'{EXP}/{n}.img')
    print(f'{n}: written={changed} nonE5={nz(d)}', flush=True)
    time.sleep(0.6)
