#!/usr/bin/env python3
"""Verify embedded fingerprint/exports against an extracted official kernel ELF.
Usage: python3 verify-firmware.py /path/to/kernel.raw
No NAS access or writes. Fixed offsets are intentional and SHA256-gated.
"""
import hashlib
from pathlib import Path
import re
import struct
import sys

root = Path(__file__).resolve().parent
data = Path(sys.argv[1]).read_bytes()
expected = '13dcb67c60a18b363d275a80adeab6dfe4ca3ce03a314bd3acf58eb54fe03637'
if hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit('REFUSED: different kernel ELF')
header = (root / 'firmware_guard.h').read_text()
array = header.split('{', 1)[1].split('}', 1)[0]
embedded = bytes(int(s, 16) for s in re.findall(r'0x[0-9a-f]{2}', array))
assert embedded == data[0x61f0f0:0x61f1b1]
lines = []
for off, size, kind in [(0x985910, 0x10e30, 'EXPORT_SYMBOL'),
                        (0x996740, 0xbcf0, 'EXPORT_SYMBOL_GPL')]:
    for p in range(off, off + size, 16):
        _, ptr = struct.unpack_from('<QQ', data, p)
        q = ptr - 0xffffffff81000000 + 0x200000
        name = data[q:data.index(b'\0', q)].decode('ascii')
        lines.append(f'0x00000000\t{name}\tvmlinux\t{kind}\n')
assert ''.join(lines) == (root / 'firmware-exports.symvers').read_text()
print(f'PASS: {len(embedded)} helper bytes and {len(lines)} actual kernel exports match')
