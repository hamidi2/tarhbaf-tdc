#!/usr/bin/env python3
"""LAENGE campaign — findings so far (2026-10-25, batch1: 43+ dosbox rounds).

LAENGE = f(w, h, machine-config-in-DEF) — TIF content is IRRELEVANT
(black/white/checker/half designs at same (w,h) → byte-identical LAENGE).

Structure (little-endian-ish fields):
  [0] = S div 256            S = ceil((512 + pitch*h) / 256)  (sector count)
  [1] = len & 0xFF
  [2] = S & 0xFF
  body (len-3-ish bytes)   = rows of `pitch` bytes (pitch = rowbytes_even+2,
                             same as MUSTER), rows mostly 0xFF with small
                             zero-gaps, or mostly 0x00 with FF-runs — pattern
                             is a pure function of (w,h) [ground weave mapping?]
  tail2 (last 2 bytes)     = [rb-1, (256-rb)&0xFF] where rb = unpadded rowbytes
                             (== BE16 of rb*255) — verified w800/1016/1648

LEN FORMULA — SOLVED (2026-10-25, verified 51/51 points, 20 widths, h∈32..768):
  len = (180 + h * ((rb mod 64) + 2)) mod 2048
  rb  = rowbytes = ceil(w/8) padded to even
  (NOTE: real 2003 sample 2224_2 (w1016,h6120) does NOT fit — probably written
   with a different 2003-era config; our target is today's config = our DEF)

OTHER SOLVED FIELDS:
  LAENGE[0] = S div 256, LAENGE[2] = S mod 256,
      S = ceil((512 + pitch*h) / 256), pitch = rb + 2   (sector count)
  LAENGE[1] = len & 0xFF
  tail2 = [rb-1, (256-rb)&0xFF]  (== BE16 of rb*255)
  body = rows of `pitch` bytes, mostly 0xFF with small zero-gaps (or inverse);
         gap position moves with h (w1016: byte 41 - (h-128)/32 for h128/256/512)

Verified examples:
  w1648 (rb206,s16): h128→180, h192→1204, h256→180, h320→1204, h448→1204,
                     h512→180, h768→180, h96→1716
  w800  (rb100,s6):  h96→1780, h128→948, h192→1332, h256→1716, h320→52,
                     h448→820, h512→1204
  w1016 (rb128,s2):  h128→436, h256→692, h512→1204

Gap position within FF rows (w1016): byte 41,37,29 for h128,256,512
  → gap_byte = 41 - (h-128)/32  (moves −1 byte per +32 rows)

TODO next:
  - fine height sweeps (step 32) per width → gap-position law + polarity flips
  - identify ground weave bitmap inside DEF (135HQ.DEF) and test resample model
  - verify len formula against fresh operator output (their config today)
  - implement generator in tdc_format.c, drop template dependency
"""
import sys, glob, re, math
sys.path.insert(0, '/home/hamidi/code/knit')
from karlmayer_tdc import BLOCK, COPYRIGHT_SIG, parse_catalog, file_blocks

def laenge_of(img):
    d = open(img, 'rb').read()
    lb = file_blocks(parse_catalog(d), 'LAENGE')
    lblk = d[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
    return lblk[:lblk.find(COPYRIGHT_SIG)]

def predict_len(w, h):
    rb = -(-w // 8)          # ceil(w/8)
    rb += rb % 2             # pad to even
    s = (rb % 32) + 2
    return (180 + s*h) % 2048

if __name__ == '__main__':
    ok = bad = 0
    for img in sorted(glob.glob('/home/hamidi/code/knit/exp/la/w*h*.img')):
        m = re.match(r'.*/w(\d+)h(\d+)\.img', img)
        w, h = int(m.group(1)), int(m.group(2))
        la = laenge_of(img)
        p = predict_len(w, h)
        mark = 'OK ' if len(la) == p else 'BAD'
        if len(la) == p: ok += 1
        else: bad += 1; print(f'{mark} w{w} h{h}: actual={len(la)} pred={p}')
    print(f'len-formula: {ok} OK, {bad} BAD')
