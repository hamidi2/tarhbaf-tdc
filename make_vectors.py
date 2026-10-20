#!/usr/bin/env python3
"""Prepare native test vectors for test_core (design rows from sample TIFs)."""
import os
from PIL import Image

S = os.path.join(os.path.dirname(__file__), 'samples')
T = os.path.join(os.path.dirname(__file__), 'testdata')
os.makedirs(T, exist_ok=True)

CASES = [('129hp_image', '129hp_design.TIF'),
         ('2224_2_image', '2224_2_design.TIF')]

def valid_in_last(W):
    return ((W - 1) % 8) + 1

for disk, tif in CASES:
    im = Image.open(os.path.join(S, tif))
    W, H = im.size
    data = im.tobytes()
    trb = (W + 7) // 8
    mask = (1 << (8 - valid_in_last(W))) - 1
    out = bytearray()
    for r in range(H):
        row = bytearray(data[r*trb:(r+1)*trb])
        row += bytes(trb - len(row))
        row[trb-1] |= mask            # margin/pad bits = white (design 1)
        out += row
    open(os.path.join(T, disk + '.rows'), 'wb').write(bytes(out))
    open(os.path.join(T, disk + '.tif'), 'wb').write(open(os.path.join(S, tif), 'rb').read())
    print(disk, W, H, 'rows.bin written')
