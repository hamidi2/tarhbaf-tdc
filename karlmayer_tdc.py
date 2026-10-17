#!/usr/bin/env python3
"""Karl Mayer TDC jacquard floppy format - reference reader/writer.

Reverse-engineered 2026-10-17 from 4 sample disks (see FORMAT.md).

Geometry: 1.44MB floppy image, 2880 sectors x 512. "Block" = 2048 bytes.
Block 0..1: directory (32-byte records). Data blocks start at block 2.

Directory record (32 bytes):
  [0]      0x00
  [1..11]  8+3 name: "MUSTER  FAC" / "LAENGE  FAC"
  [12]     seq 0..31 within group   [13] 0x00
  [14]     group (blocks = grp*256 + 2 + seq*8 ...)
  [15]     flag = 0x10 * valid_block_count_in_this_record
  [16..31] up to 8 block numbers, u16 LE; unused slots = 0xE5E5

MUSTER.FAC file (block 2..): ASCII header + 0x00 + param block (90 B)
  + bitmap rows (bottom-up) + copyright trailer (1868 B).

Row: packed width bits (p[8..9], multiple of 8), MSB first, pad bits 0,
  then 2-byte BE sum16 checksum of the row bytes. Row pitch (incl. checksum,
  rounded to even) in p[21..22] LE.

LAENGE.FAC: opaque content (length varies; up to copyright signature)
  + trailer (1868 B).

Trailer: 1868 bytes starting "Copyright (C) KARL MAYER ..." (boilerplate).
Unused disk areas: 0xE5.
"""

BLOCK = 2048
DISK = 2880 * 512
TRAILER = 1868
COPYRIGHT_SIG = b'Copyright (C) KARL MAYER'

def parse_catalog(disk):
    recs = []
    off = 0
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
        seq = rec[12]
        grp = rec[14]
        flag = rec[15]
        n = flag // 0x10
        blocks = [int.from_bytes(rec[16+2*i:18+2*i], 'little') for i in range(n)]
        recs.append({'name': name, 'seq': seq, 'grp': grp, 'flag': flag,
                     'blocks': blocks})
        off += 32
    return recs

def file_blocks(recs, name):
    out = []
    for r in recs:
        if r['name'].split()[0] == name:
            out += r['blocks']
    return out

def parse_ascii_header(data):
    lines = data.split(b'\r\n\x00')[0].split(b'\r\n')
    fields = {}
    for ln in lines:
        if b':' in ln:
            k, v = ln.split(b':', 1)
            fields[k.decode('latin1').strip()] = v.decode('latin1').strip()
    return fields

def parse_params(par):
    be = lambda b: int.from_bytes(b, 'big')
    return {
        'ndisks': par[2],
        'thisdisk': par[3],
        'width_bits': be(par[8:10]),      # multiple of 8
        'height': be(par[10:12]),
        'first_row_1based': be(par[12:14]),  # counted from bottom
        'rows_this_disk': be(par[14:16]),
        'pitch': int.from_bytes(par[21:23], 'little'),
        'disk1_rows': be(par[24:26]),
        'disk2_start_1based': be(par[26:28]),
        'disk2_rows': be(par[28:30]),
        'height2': be(par[42:44]),
        'width_px': be(par[62:64]),
        'tail': par[88],
    }

def read_design(disk):
    """Returns dict with name, width_px, height, rows (list of bytes, TOP first),
    plus raw template pieces."""
    recs = parse_catalog(disk)
    mb = file_blocks(recs, 'MUSTER')
    lb = file_blocks(recs, 'LAENGE')
    start = mb[0] * BLOCK
    data = b''.join(disk[b*BLOCK:(b+1)*BLOCK] for b in mb)
    e = data.find(b'\r\n\x00')
    hdr_txt = data[:e+2]
    par = data[e+3:e+3+90]
    p = parse_params(par)
    pitch = p['pitch']
    base = e + 3 + 90
    rows = []
    nrows = p['rows_this_disk']
    for i in range(nrows):          # i=0 -> bottom-most row of this disk
        off = base + i * pitch
        row = data[off:off + p['width_bits'] // 8]
        rows.append(row)
    rows.reverse()                  # top-first
    # LAENGE opaque content (up to copyright signature)
    lcontent = b''
    if lb:
        lblk = disk[lb[0]*BLOCK:(lb[0]+1)*BLOCK]
        ci = lblk.find(COPYRIGHT_SIG)
        lcontent = lblk[:ci if ci >= 0 else 180]
    return {
        'info': parse_ascii_header(hdr_txt),
        'params': p, 'rows': rows, 'laenge': lcontent,
        'trailer': disk[(mb[-1]*BLOCK + ((base + nrows*pitch - 1) % BLOCK + 1))
                        if False else 0:0] or find_trailer(disk, mb, base, nrows, pitch),
        'catalog': recs,
    }

def find_trailer(disk, mb, base, nrows, pitch):
    # trailer starts right after content end (sequential rule of clean saves)
    end_off = base + nrows * pitch          # within file data
    fdata = b''.join(disk[b*BLOCK:(b+1)*BLOCK] for b in mb)
    return fdata[end_off:end_off + TRAILER]

def build_catalog(muster_nblocks, laenge_block):
    """Directory records for one MUSTER + one LAENGE file, fresh save."""
    recs = b''
    seq = 0
    grp = 0
    left = muster_nblocks
    blk = 2
    while left > 0:
        take = min(8, left)
        flag = 0x10 * take if take < 8 or left - take == 0 else 0x80
        rec = bytearray(b'\xe5' * 32)
        rec[0] = 0
        rec[1:12] = b'MUSTER  FAC'
        rec[12] = seq
        rec[13] = 0
        rec[14] = grp
        rec[15] = flag
        for i in range(take):
            rec[16+2*i:18+2*i] = (blk + i).to_bytes(2, 'little')
        recs += bytes(rec)
        blk += take
        left -= take
        seq += 1
        if seq == 32:
            seq = 0
            grp += 1
    rec = bytearray(b'\xe5' * 32)
    rec[0] = 0
    rec[1:12] = b'LAENGE  FAC'
    rec[12] = 0
    rec[13] = 0
    rec[14] = 0
    rec[15] = 0x10
    rec[16:18] = laenge_block.to_bytes(2, 'little')
    recs += bytes(rec)
    return recs

def make_ascii_header(name, date):
    def f(v):
        v = v.encode('latin1')[:13]
        return v + b' ' * (13 - len(v))
    return (b'MASCHINENTYP :' + f('JACQUARD') + b'\r\n'
            b'Muster...... : ' + f(name) + b'\r\n'
            b'Datum....... : ' + f(date) + b'\r\n'
            b'\x00')

def row_bytes(bits_packed):
    """bits_packed: bytes of design row (MSB first, pad bits already 0).
    Stored = inverted bits, padded to even length, + 2-byte BE sum16."""
    inv = bytearray(b ^ 0xFF for b in bits_packed)
    if len(inv) % 2:
        inv.append(0)
    return bytes(inv) + (sum(inv) & 0xFFFF).to_bytes(2, 'big')

def build_disk(rows_top_first, width_bits, width_px, height, name, date,
               template, ndisks, thisdisk, rows_this_disk,
               disk1_rows, disk2_start, disk2_rows, disk_capacity_blocks):
    """Build one floppy image. rows_top_first: list of packed row bytes
    (MSB-first, width_bits//8 each) from design TOP to BOTTOM (this disk's
    slice). template: dict with 'param' (90 B), 'laenge' (opaque bytes),
    'trailer' (1868 B)."""
    dbytes = width_bits // 8
    pitch = (dbytes + 1) // 2 * 2 + 2            # pad data to even, +2 checksum
    hdr = make_ascii_header(name, date)
    par = bytearray(template['param'][:88])
    par[2] = ndisks
    par[3] = thisdisk
    par[8:10] = width_bits.to_bytes(2, 'big')
    par[10:12] = height.to_bytes(2, 'big')
    par[12:14] = (disk2_start.to_bytes(2, 'big') if thisdisk == 2
                  else b'\x00\x01')
    par[14:16] = rows_this_disk.to_bytes(2, 'big')
    par[21:23] = pitch.to_bytes(2, 'little')
    par[24:26] = disk1_rows.to_bytes(2, 'big')
    par[26:28] = disk2_start.to_bytes(2, 'big')
    par[28:30] = disk2_rows.to_bytes(2, 'big')
    par[42:44] = height.to_bytes(2, 'big')
    par[62:64] = width_px.to_bytes(2, 'big')
    chk = (sum(hdr) + sum(par)) & 0xFFFF           # hdr(incl 0x00) + param[0:88]
    param = bytes(par) + chk.to_bytes(2, 'big')

    body = hdr + param
    first_row_1based_from_bottom = disk2_start if thisdisk == 2 else 1
    ordered = reversed(rows_top_first)             # bottom first
    for rb in ordered:
        body += row_bytes(rb)
    nblocks = (len(body) + BLOCK - 1) // BLOCK
    # clamp to capacity (caller ensures fit)
    laenge_block = 2 + nblocks
    disk = bytearray(b'\xe5' * DISK)
    disk[0:len(build_catalog(nblocks, laenge_block))] = build_catalog(nblocks, laenge_block)
    pos = 2 * BLOCK
    disk[pos:pos+len(body)] = body
    pos += len(body)
    # trailer: fill remainder of the current block, truncated at block end
    n = min(len(template['trailer']), ((pos // BLOCK) + 1) * BLOCK - pos)
    disk[pos:pos+n] = template['trailer'][:n]
    pos = laenge_block * BLOCK
    lcontent = template['laenge']
    disk[pos:pos+len(lcontent)] = lcontent
    pos += len(lcontent)
    n = min(len(template['trailer']), ((pos // BLOCK) + 1) * BLOCK - pos)
    disk[pos:pos+n] = template['trailer'][:n]
    return bytes(disk)
