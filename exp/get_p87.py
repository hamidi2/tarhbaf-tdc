import sys
d = open(sys.argv[1],'rb').read()
i = d.find(b'MASCHINENTYP :JACQUARD')
hdr = d[i:i+90] if i >= 0 else b''
name = hdr[44:57].decode('latin1').rstrip().strip('\x00') if hdr else '?'
date = hdr[74:87].decode('latin1').rstrip().strip('\x00') if hdr else '?'
# param search: signature + valid width + valid header-chk
best = None
for s in range(len(d) - 90):
    if d[s:s+4] != b'\x11\x02\x01\x01':
        continue
    w = int.from_bytes(d[s+8:s+10], 'big')
    if w not in (800, 1000, 1015, 1016, 1200, 1585, 1592, 1648, 800+16, 1000+24):
        continue
    # find a header candidate 90 bytes before (contiguous case) or verify via chk over nearest header
    # checksum validation: need hdr; try the found hdr
    if i >= 0:
        chk_calc = (sum(hdr[:90]) ) & 0xFFFF   # hdr includes trailing 0x00 at hdr[87]..? approximate
    best = (s, w, d[s+87])
    break
if best:
    print(f"{name!r:16} {date!r:12} p87={best[2]:#04x} w={best[1]} (param@{best[0]})")
else:
    print("no param found")
