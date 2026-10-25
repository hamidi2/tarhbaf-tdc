#!/usr/bin/env python3
"""Generate FAKEDATE.COM — a 16-bit DOS TSR hooking INT 1Ah and INT 21h to
return a fake date (set via argv). Usage: gen_fakedate.py YYYY MM DD out.com"""
import sys

yy, mm, dd = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
bcd = lambda v: ((v//10) << 4) | (v % 10)
if not (1980 <= yy <= 2099):
    sys.exit("year out of range")
import datetime
dow = datetime.date(yy, mm, dd).weekday() + 1 & 7   # DOS: 0=Sun

new1a = bytes([
    0x80, 0xFC, 0x04,             # cmp ah,04
    0x75, 0x11,                   # jne skip1a
    0xB5, bcd(yy // 100),         # mov ch,century (BCD)
    0xB1, bcd(yy % 100),          # mov cl,year (BCD)
    0xB6, bcd(mm),                # mov dh,month (BCD)
    0xB2, bcd(dd),                # mov dl,day (BCD)
    0x55,                         # push bp
    0x89, 0xE5,                   # mov bp,sp
    0x83, 0x66, 0x06, 0xFE,       # and word [bp+6],~CF  (clear carry)
    0x5D,                         # pop bp
    0xCF,                         # iret
])
assert len(new1a) == 0x16, len(new1a)
skip1a = bytes([0x2E, 0xFF, 0x2E]) + (0x130).to_bytes(2, 'little')  # jmp far [cs:old1a]

new21 = bytes([
    0x80, 0xFC, 0x2A,             # cmp ah,2A
    0x75, 0x0A,                   # jne skip21
    0xB9]) + yy.to_bytes(2, 'little') + bytes([
    0xB6, mm,                     # mov dh,month
    0xB2, dd,                     # mov dl,day
    0xB0, dow,                    # mov al,dayofweek
    0xCF,                         # iret
])
assert len(new21) == 0x0F, len(new21)
skip21 = bytes([0x2E, 0xFF, 0x2E]) + (0x134).to_bytes(2, 'little')  # jmp far [cs:old21]

o1a, o21 = 0x100, 0x100 + 0x16 + 5          # new1a, new21 file offsets
w16 = lambda v: v.to_bytes(2, 'little')
init = (bytes([0xB8, 0x1A, 0x35, 0xCD, 0x21]) +        # ax=351a get int1a
        bytes([0x2E, 0x89, 0x1E, 0x30, 0x00]) +        # mov [cs:130],bx
        bytes([0x2E, 0x8C, 0x06, 0x32, 0x00]) +        # mov [cs:132],es
        bytes([0xB8, 0x1A, 0x25, 0xBA]) + w16(o1a) + bytes([0xCD, 0x21]) +
        bytes([0xB8, 0x21, 0x35, 0xCD, 0x21]) +        # ax=3521
        bytes([0x2E, 0x89, 0x1E, 0x34, 0x00]) +        # mov [cs:134],bx
        bytes([0x2E, 0x8C, 0x06, 0x36, 0x00]) +        # mov [cs:136],es
        bytes([0xB8, 0x21, 0x25, 0xBA]) + w16(o21) + bytes([0xCD, 0x21]) +
        bytes([0xBA, 0x38, 0x00, 0xCD, 0x27]))         # mov dx,138 / int 27

com = new1a + skip1a + new21 + skip21 + b'\x00' * 9 + init
assert len(com) == 0x38 + len(init), (hex(len(com)), hex(len(init)))
open(sys.argv[4], 'wb').write(com)
print(f"wrote {sys.argv[4]} ({len(com)} bytes) for {dd:02d}.{mm:02d}.{yy}")
