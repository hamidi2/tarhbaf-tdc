#!/usr/bin/env python3
"""ساخت فلاپی کاملاً سینتتیک (MUSTER با هستهٔ شناخته‌شده + LAENGE با مولد خودمان)
برای تست پذیرش PC-CONV: usage: make_synth.py w h out.img"""
import sys, math
sys.path.insert(0, '/home/hamidi/code/knit')
import numpy as np
from PIL import Image
from karlmayer_tdc import BLOCK, COPYRIGHT_SIG, parse_catalog, file_blocks

def gen_laenge(w, h, var4=b'\x00'*4):
    wpb = -(-w//8); rb = wpb + (wpb%2); p = rb+2
    L = (180 + ((rb%64)+2)*h) % 2048
    S = (640+p*h)//256
    if rb == wpb: sep = bytes([(rb-1)&0xFF, (256-rb)&0xFF])
    else: sep = bytes([0, (wpb-1)&0xFF, (256-wpb)&0xFF])
    out = bytearray([S//256, L%256, S%256]) + bytearray(b'\x00'*(L-3))
    zb = L-1556; blobend = 3
    if zb >= 3 and zb+20 <= L-3:
        out[zb:zb+20] = b'\x04\x00\x00\x02\x0e\x6e\x78\x6e\x61\x6c\x18\x12\x00\x00\x00\x00' + var4
        blobend = zb+20
    ph = (L - len(sep)) % p
    s0 = ph
    while s0 < blobend: s0 += p
    seps = list(range(s0, L-len(sep)+1, p))
    for i in range(blobend, L):
        if out[i] == 0: out[i] = 0xFF
    for s in seps: out[s:s+len(sep)] = sep
    return bytes(out)

def trailer_of(ref_img):
    d = open(ref_img,'rb').read()
    mb = file_blocks(parse_catalog(d), 'MUSTER')
    data = b''.join(d[b*BLOCK:(b+1)*BLOCK] for b in mb)
    # trailer از انتهای محتوا تا پایان بلوک؛ کل تریلر مرجع: بلوک‌های انتهایی
    # ساده: از فلاپی خالی? خیر — تریلر را از مرجع برداریم: بعد از اولین COPYRIGHT تا 1868
    ci = data.find(COPYRIGHT_SIG)
    # انتهای data = انتهای بلوک آخر
    end = len(data)
    return data[ci:end]

def main():
    w, h, out, ref = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
    wpb = -(-w//8); rb = wpb + (wpb%2); pitch = rb+2
    disk = bytearray(b'\xe5' * 1474560)
    refd = open(ref,'rb').read()
    mbref = file_blocks(parse_catalog(refd), 'MUSTER')
    refdata = b''.join(refd[b*BLOCK:(b+1)*BLOCK] for b in mbref)
    e = refdata.find(b'\r\n\x00')
    hdr = bytearray(refdata[:e+3])
    # نام و تاریخ
    hdr[44:57] = b'AAA'.ljust(13)
    hdr[74:87] = b'25.10.26'.ljust(12)
    hdr[87] = 0
    par = bytearray(refdata[e+3:e+3+90])
    # rows
    img = (np.array(Image.open('/home/hamidi/code/knit/exp/la/t.tif').convert('1')) > 0)
    dbytes = wpb
    body = bytearray(hdr + par)
    for r in range(h):
        src = img[h-1-r]
        packed = np.packbits(src).tobytes()
        row = bytes(b ^ 0xFF for b in packed)
        row += b'\x00' * (rb - len(packed))
        s = sum(row) & 0xFFFF
        row += s.to_bytes(2,'big')
        body += row
    # trailer: از مرجع، 1868 بایت بعد از انتهای محتوا — ولی مرجع scatter دارد؛
    # ساده: تریلر = نسخهٔ مرجع از بلوک انتهایی MUSTER (از ci تا end-of-block)
    ci = refdata.find(COPYRIGHT_SIG)
    # تریلر کامل: از بلوک انتهایی MUSTER مرجع
    lastblk = mbref[-1]
    blkdata = refd[lastblk*BLOCK:(lastblk+1)*BLOCK]
    tci = blkdata.find(COPYRIGHT_SIG)
    trailer = blkdata[tci:]  # تا انتهای بلوک (بریده مثل real)
    nblocks = (len(body)+BLOCK-1)//BLOCK
    cat = bytearray(BLOCK*2)
    def rec(name, seq, nfull, blocks):
        r = bytearray(32)
        r[1:12] = name
        r[12] = seq; r[14] = 0
        r[15] = nfull * 16
        for i, b in enumerate(blocks[:8]):
            r[16+2*i:18+2*i] = b.to_bytes(2,'little')
        return bytes(r)
    recs = []
    blk = 2; remaining = nblocks; seq = 0
    while remaining > 0:
        take = min(8, remaining)
        bl = list(range(blk, blk+take)) + [0xE5E5]*(8-take)
        recs.append(rec(b'MUSTER  FAC', seq, take, bl))
        blk += take; remaining -= take; seq += 1
    la = gen_laenge(w, h)
    la_nb = (len(la)+BLOCK-1)//BLOCK
    lblk = list(range(blk, blk+la_nb))
    lrec = rec(b'LAENGE  FAC', 0, la_nb, lblk + [0xE5E5]*(8-la_nb))
    for i, r in enumerate(recs):
        cat[i*32:(i+1)*32] = r
    cat[len(recs)*32:len(recs)*32+32] = lrec
    disk[0:BLOCK*2] = cat
    disk[2*BLOCK:2*BLOCK+len(body)] = body
    # LAENGE block + trailer
    ldata = la + trailer
    ldata = ldata[:len(lblk)*BLOCK]
    disk[lblk[0]*BLOCK:lblk[0]*BLOCK+len(ldata)] = ldata
    open(out,'wb').write(bytes(disk))
    print(f'synthetic {out}: w={w} h={h} musterb={nblocks} la={len(la)}@{lblk[0]}')

main()
