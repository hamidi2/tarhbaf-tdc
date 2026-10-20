#!/usr/bin/env python3
"""test_same.py —simulate the GUI v2 path for the operator's exact use case and
verify the output is byte-identical to the DOS reference EXCEPT the date bytes
(+ the param checksum that covers the header), which the DOS program itself
would stamp with today's date when re-saving."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from karlmayer_tdc import (BLOCK, TRAILER, COPYRIGHT_SIG, parse_catalog,
                           file_blocks, parse_params, parse_ascii_header,
                           make_ascii_header, row_bytes, build_catalog, DISK)
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, 'samples')
REF = os.path.join(S, '2224_2_image')
TIF = os.path.join(S, '2224_2_design.TIF')

disk = open(REF, 'rb').read()

# --- embedded template pieces exactly like tdc_embedded.h / make_embedded.py
recs = parse_catalog(disk)
mb = file_blocks(recs, 'MUSTER')
lb = file_blocks(recs, 'LAENGE')
data = b''.join(disk[b*BLOCK:(b+1)*BLOCK] for b in mb)
e = data.find(b'\r\n\x00')
par = data[e+3:e+3+90]
p = parse_params(par)
dbytes = p['width_bits'] // 8
pitch = (dbytes + 1) // 2 * 2 + 2
content_end = e + 3 + 90 + p['rows_this_disk'] * pitch
inblk = content_end % BLOCK
trailer = data[content_end:content_end + min(TRAILER, BLOCK - inblk)]
lblk = disk[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
laenge = lblk[:lblk.find(COPYRIGHT_SIG)]
emb_param88 = bytearray(par[:88])

# --- GUI-equivalent rows from the TIF (1015 wide -> width_bits 1016)
im = Image.open(TIF)
W, H = im.size
assert W == p['width_px'] and H == p['height']
tifb = im.tobytes()
trb = (W + 7) // 8
valid_last = ((W - 1) % 8) + 1
mask = (1 << (8 - valid_last)) - 1
rows = []
for r in range(H):
    row = bytearray(tifb[r*trb:(r+1)*trb])
    row += bytes(dbytes - len(row))
    row[trb-1] |= mask            # margin/pad = white
    rows.append(bytes(row))

# --- build with the GUI defaults: name typed by operator, TODAY's date
NAME, DATE = '2224_2', '18.10.26'
hdr = make_ascii_header(NAME, DATE)
par88 = bytearray(emb_param88)
par88[2] = 1
par88[3] = 1
def be16(v): return v.to_bytes(2, 'big')
par88[8:10]  = be16(p['width_bits'])
par88[10:12] = be16(H)
par88[12:14] = b'\x00\x01'
par88[14:16] = be16(H)
def le16(v): return v.to_bytes(2, 'little')
par88[21:23] = le16(pitch)
par88[24:26] = be16(H)
par88[26:28] = be16(0)
par88[28:30] = be16(0)
par88[42:44] = be16(H)
par88[62:64] = be16(W)
chk = (sum(hdr) + sum(par88)) & 0xFFFF
param = bytes(par88) + chk.to_bytes(2, 'big')

body = hdr + param
for r in reversed(rows):
    body += row_bytes(r)
nblocks = (len(body) + BLOCK - 1) // BLOCK
laenge_block = 2 + nblocks

out = bytearray(b'\xe5' * DISK)
cat = build_catalog(nblocks, laenge_block)
out[0:len(cat)] = cat
pos = 2 * BLOCK
out[pos:pos+len(body)] = body
pos += len(body)
n = min(len(trailer), ((pos // BLOCK) + 1) * BLOCK - pos)
out[pos:pos+n] = trailer[:n]
pos = laenge_block * BLOCK
out[pos:pos+len(laenge)] = laenge
pos += len(laenge)
n = min(len(trailer), ((pos // BLOCK) + 1) * BLOCK - pos)
out[pos:pos+n] = trailer[:n]

# --- diff vs reference
diffs = [i for i in range(DISK) if out[i] != disk[i]]
print("diff bytes vs DOS reference:", len(diffs))
hdr_off = 2*BLOCK
date_bytes = set(range(hdr_off+74, hdr_off+82))          # "21.05.03" -> "18.10.26"
chk_bytes = set(range(hdr_off+90+88, hdr_off+90+90))     # param checksum covers header
unexpected = [i for i in diffs if i not in date_bytes | chk_bytes]
print("date bytes:", sorted(i-hdr_off for i in diffs if i in date_bytes))
print("checksum bytes:", sorted(i-hdr_off for i in diffs if i in chk_bytes))
print("UNEXPECTED:", unexpected[:20])
if not unexpected and len(diffs) <= 10:
    print("PASS: output is identical to the DOS reference except today's date (+its checksum)")
    open(os.path.join(os.path.expanduser('~/dl/td'), '2224_2-v2-hamidi.img'), 'wb').write(bytes(out))
    print("written: ~/dl/td/2224_2-v2-hamidi.img")
    sys.exit(0)
sys.exit(1)
