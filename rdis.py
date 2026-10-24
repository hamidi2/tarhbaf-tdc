#!/usr/bin/env python3
"""Recursive-descent disassembler for the PC-CONV MZ module (16-bit x86).
Follows control flow from the entry point; writes clean disasm to /tmp/rdis.asm"""
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_16

EXE = '/home/hamidi/code/knit/dosrun/PC-CONV.EXE'
d = open(EXE, 'rb').read()
cblp, cp, crlc, cparhdr = struct.unpack('<HHHH', d[2:10])
hdr = cparhdr * 16
mod = d[hdr:]
CS_BASE = 0x1000          # load segment assumption for display only
ENTRY_OFF = struct.unpack('<H', d[0x14:0x16])[0]
ENTRY_REL = struct.unpack('<H', d[0x16:0x18])[0] * 16   # in paragraphs
entry = ENTRY_REL + ENTRY_OFF - 0  # module-relative flat offset
print(f"module={len(mod):#x} entry_rel={ENTRY_REL:#x} entry_ip={ENTRY_OFF:#x} -> flat {entry:#x}")

md = Cs(CS_ARCH_X86, CS_MODE_16)
md.detail = True

visited = {}   # offset -> (insn)
worklist = [entry]
# seed: همهٔ مقصدهای call rel16 (E8) از اسکن بایتی
import struct as _s
seeded = set()
for i in range(len(mod)-3):
    if mod[i] == 0xE8:
        rel = _s.unpack('<h', mod[i+1:i+3])[0]
        t = i + 3 + rel
        if 0 <= t < len(mod)-16 and t not in seeded:
            seeded.add(t); worklist.append(t)
CALLTARGETS = set()

def regval(op):
    return op.reg

while worklist:
    off = worklist.pop()
    while True:
        if off in visited or off < 0 or off >= len(mod) - 16:
            break
        try:
            ins = next(md.disasm(mod[off:off+16], off))
        except StopIteration:
            break
        visited[off] = ins
        m = ins.mnemonic
        if m in ('jmp',):
            t = None
            if ins.operands and ins.operands[0].type == 2:  # imm
                t = ins.operands[0].imm
            if t is not None and 0 <= t < len(mod):
                worklist.append(t)
            break
        if m.startswith('j'):          # conditional jumps: fall through + target
            if ins.operands and ins.operands[0].type == 2:
                t = ins.operands[0].imm
                if 0 <= t < len(mod):
                    worklist.append(t)
            off += ins.size
            continue
        if m in ('call', 'lcall'):
            if ins.operands and ins.operands[0].type == 2:
                t = ins.operands[0].imm
                if 0 <= t < len(mod):
                    CALLTARGETS.add(t)
                    worklist.append(t)
            off += ins.size
            continue
        if m in ('ret', 'retf', 'iret', 'int3', 'hlt', 'jmpf'):
            break
        off += ins.size

print(f"decoded {len(visited)} instructions, {len(CALLTARGETS)} call targets")
with open('/tmp/rdis.asm', 'w') as f:
    for off in sorted(visited):
        ins = visited[off]
        mark = 'F:' if off in CALLTARGETS else '  '
        f.write(f"{mark}{off:06x}  {ins.mnemonic:8} {ins.op_str}\n")
print("wrote /tmp/rdis.asm")
