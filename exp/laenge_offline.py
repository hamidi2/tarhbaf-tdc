#!/usr/bin/env python3
"""LAENGE campaign step 1: offline analysis.
Collect (TIF, LAENGE-block) pairs from exp/*.img and try transforms of the TIF
that could produce the LAENGE bytes."""
import os, sys, glob
import numpy as np
from PIL import Image

HOME = os.path.expanduser('~')
KNIT = f'{HOME}/code/knit'
sys.path.insert(0, KNIT)
from karlmayer_tdc import BLOCK, COPYRIGHT_SIG, parse_catalog, file_blocks

def extract_laenge(img):
    d = open(img, 'rb').read()
    recs = parse_catalog(d)
    if not recs:
        return None
    lb = file_blocks(recs, 'LAENGE')
    if not lb:
        return None
    lblk = d[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
    ci = lblk.find(COPYRIGHT_SIG)
    if ci < 0:
        return None
    return lblk[:ci]  # content before copyright sig

def tif_bits(path):
    return (np.array(Image.open(path).convert('1')) > 0)

pairs = []
for img in sorted(glob.glob(f'{KNIT}/exp/*.img')):
    la = extract_laenge(img)
    if la is None:
        continue
    tif = img.replace('.img', '.tif')
    if not os.path.exists(tif):
        continue
    pairs.append((os.path.basename(img), tif, la))

# also harness real reference imgs with known TIFs
for name, tif in [('r129hp', f'{KNIT}/samples/129hp_design.TIF'),
                  ('r2224_2', f'{KNIT}/samples/2224_2_design.TIF')]:
    img = f'{KNIT}/harness/{name}.tif'
    if os.path.exists(img):
        la = extract_laenge(img)
        if la:
            pairs.append((name, tif, la))

print(f'{len(pairs)} pairs with LAENGE:')
for name, tif, la in pairs:
    w, h = Image.open(tif).size
    print(f'  {name:22} tif={w}x{h}  laenge_len={len(la)}  head={la[:8].hex()} tail={la[-8:].hex()}')

np.save('/tmp/la_pairs.npy', np.array([(n, t) for n, t, _ in pairs], dtype=object), allow_pickle=True)
import pickle
pickle.dump([(n, t, la) for n, t, la in pairs], open('/tmp/la_pairs.pkl', 'wb'))
