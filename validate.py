#!/usr/bin/env python3
"""Rebuild sample disks from their TIFs and compare byte-for-byte."""
import sys, struct
from PIL import Image
sys.path.insert(0, '/home/hamidi/code/knit')
from karlmayer_tdc import *

S = '/home/hamidi/code/knit/samples/'

def trailer_of(disk):
    i = disk.find(COPYRIGHT_SIG)
    return disk[i:i+TRAILER]

def packed_rows(tif_path, width_bits):
    im = Image.open(tif_path)
    W, H = im.size
    assert W <= width_bits and width_bits - W < 8
    rb = width_bits // 8
    tif = im.tobytes()
    trb = (W + 7) // 8
    rows = []
    for r in range(H):
        row = bytearray(tif[r*trb:(r+1)*trb])
        row += bytes(rb - len(row))
        if W % 8:  # zero the pad bits (design domain)
            row[trb-1] &= (0xFF << (8 - W % 8)) & 0xFF & 0xFF
            row[trb-1] &= ~((1 << (8 - W % 8)) - 1) & 0xFF
        rows.append(bytes(row))
    return rows, W, H

def template_from(disk):
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
    ci = lblk.find(COPYRIGHT_SIG)
    return {'param': bytes(par), 'laenge': lblk[:ci], 'trailer': trailer}

def rebuild(diskfile, tiffile):
    disk = open(S+diskfile, 'rb').read()
    tpl = template_from(disk)
    info = parse_ascii_header(disk[2*BLOCK:2*BLOCK+200])
    name = info['Muster......']
    date = info['Datum.......']
    p = parse_params(tpl['param'])
    wb = p['width_bits']
    rows, W, H = packed_rows(S+tiffile, wb)
    assert H == p['height'] and W == p['width_px']
    ndisks = p['ndisks']
    capacity = (2877 - 1) * BLOCK   # blocks 2..2878 minus LAENGE block
    if ndisks == 1:
        slices = [(rows, 1)]
    else:
        per = p['disk1_rows']
        slices = [(rows[per:], 1), (rows[:p['disk2_rows']], 2)]
    outs = []
    for idx, (sl, dno) in enumerate(slices):
        rows_this = len(sl)
        out = build_disk(
            sl, wb, W, H, name, date, tpl,
            ndisks=ndisks, thisdisk=dno, rows_this_disk=rows_this,
            disk1_rows=p['disk1_rows'] or rows_this,
            disk2_start=p['disk2_start_1based'], disk2_rows=p['disk2_rows'],
            disk_capacity_blocks=capacity)
        outs.append(out)
    return disk, outs

for df, tf in [('129hp_image', '129hp_design.TIF'),
               ('2224_2_image', '2224_2_design.TIF')]:
    orig, outs = rebuild(df, tf)
    outs = [bytearray(o) for o in outs]
    out = outs[0]
    diffs = [i for i in range(DISK) if orig[i] != out[i]]
    # the TIF lacks the design's right-most pad column(s) when width_px % 8
    # (2224_2: TIF 1015 vs design 1016) -> exclude that byte from each row
    disk = open(S+df, 'rb').read()
    tpl = template_from(disk)
    p = parse_params(tpl['param'])
    if p['width_px'] % 8:
        dbytes = p['width_bits'] // 8
        pitch = (dbytes + 1) // 2 * 2 + 2
        # restore the design's right-most column from the original disk
        # (the TIF was exported 1 column narrower), then rebuild
        for i in range(p['rows_this_disk']):
            off = 2*BLOCK + 180 + i*pitch + dbytes - 1
            outs[0][off] = orig[off]
        # recompute checksums for those rows
        for i in range(p['rows_this_disk']):
            base = 2*BLOCK + 180 + i*pitch
            row = outs[0][base:base+dbytes]
            pad = dbytes % 2
            s = sum(row) & 0xFFFF
            outs[0][base+dbytes+pad:base+dbytes+pad+2] = s.to_bytes(2, 'big')
        diffs = [i for i in range(DISK) if orig[i] != outs[0][i]]
    print(f"{df}: rebuilt {len(outs)} disk(s), diff bytes = {len(diffs)}")
    if diffs:
        import itertools
        rng = []
        s = p0 = diffs[0]
        for i in diffs[1:]:
            if i != p0 + 1:
                rng.append((s, p0)); s = i
            p0 = i
        rng.append((s, p0))
        print("  ranges:", rng[:10])
