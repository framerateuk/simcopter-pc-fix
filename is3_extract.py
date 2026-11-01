#!/usr/bin/env python3
"""Extract an InstallShield 3 "Z" archive (_SETUP.1 and the like) without running SETUP.EXE.

    python3 -I is3_extract.py <archive> <out_dir> [-l]

(build.py imports it to unpack the disc's v1.02 patch.)

Layout (read from Ultimate Race's _SETUP.1, matches deark's notes on the format):
header u32 0x8C655D13, u16 file count at 0x0C, u32 directory table at 0x29 (u16 size at 0x2D,
u16 count at 0x31), u32 file table at 0x33. Directory entry: u16 files, u16 entry size, u16 name
length, name. File entry: u8, u16 directory index, u32 size, u32 packed size, u32 offset, u16 date,
u16 time, u32 attributes, u16 entry size, u32, u8 name length, name. Data: PKWARE DCL implode.
"""
import os
import struct
import sys


class _Bits:
    def __init__(self, data):
        self.data, self.pos, self.buf, self.cnt = data, 0, 0, 0

    def bits(self, n):
        while self.cnt < n:
            self.buf |= self.data[self.pos] << self.cnt
            self.pos += 1
            self.cnt += 8
        v = self.buf & ((1 << n) - 1)
        self.buf >>= n
        self.cnt -= n
        return v


def _table(rep):
    """Huffman decoder from blast.c's compact run-length code-length list."""
    lengths = []
    for b in rep:
        lengths += [(b & 15)] * ((b >> 4) + 1)
    codes = {}
    # blast.c builds canonical codes, then reads them bit-reversed (LSB first)
    code = 0
    for ln in range(1, 14):
        for sym, l in enumerate(lengths):
            if l == ln:
                codes[(ln, code)] = sym
                code += 1
        code <<= 1
    return codes


def _decode(b, codes):
    code = ln = 0
    while True:
        code |= b.bits(1) ^ 1   # blast.c inverts the bits
        ln += 1
        sym = codes.get((ln, code))
        if sym is not None:
            return sym
        code <<= 1
        if ln > 13:
            raise ValueError('bad code')


_LITLEN = bytes([11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8, 9, 7, 6, 7, 8, 7,
                 6, 55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5, 7, 24, 6, 11, 9, 6, 7, 22, 5, 11,
                 38, 7, 9, 8, 25, 11, 8, 11, 9, 12, 8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53,
                 8, 7, 24, 10, 27, 44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45,
                 44, 173])
_LENLEN = bytes([2, 35, 36, 53, 38, 23])
_DISTLEN = bytes([2, 20, 53, 230, 247, 151, 248])
_BASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264]
_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]
_LIT, _LEN, _DIST = _table(_LITLEN), _table(_LENLEN), _table(_DISTLEN)


def explode(data):
    """PKWARE Data Compression Library decompressor (after zlib's contrib/blast)."""
    b = _Bits(data)
    lit = b.bits(8)
    dictbits = b.bits(8)
    if lit > 1 or not 4 <= dictbits <= 6:
        raise ValueError('not DCL implode data')
    out = bytearray()
    while True:
        if b.bits(1):
            sym = _decode(b, _LEN)
            ln = _BASE[sym] + b.bits(_EXTRA[sym])
            if ln == 519:
                return bytes(out)
            sym = 2 if ln == 2 else dictbits
            dist = (_decode(b, _DIST) << sym) + b.bits(sym) + 1
            for _ in range(ln):
                out.append(out[-dist])
        else:
            out.append(_decode(b, _LIT) if lit else b.bits(8))


def entries(z):
    if struct.unpack_from('<I', z, 0)[0] != 0x8C655D13:
        raise SystemExit('not an InstallShield 3 archive')
    nfiles = struct.unpack_from('<H', z, 0x0C)[0]
    dtab, = struct.unpack_from('<I', z, 0x29)
    ndirs, = struct.unpack_from('<H', z, 0x31)
    ftab, = struct.unpack_from('<I', z, 0x33)
    dirs, p = [], dtab
    for _ in range(ndirs):
        _, esize, nlen = struct.unpack_from('<HHH', z, p)
        dirs.append(z[p + 6:p + 6 + nlen].decode('latin-1'))
        p += esize
    p = ftab
    for _ in range(nfiles):
        d, size, packed, off = struct.unpack_from('<HIII', z, p + 1)
        esize, = struct.unpack_from('<H', z, p + 23)
        nlen = z[p + 29]
        name = z[p + 30:p + 30 + nlen].decode('latin-1')
        yield dirs[d], name, size, packed, off
        p += esize


def main():
    args = [a for a in sys.argv[1:] if a != '-l']
    z = open(args[0], 'rb').read()
    for d, name, size, packed, off in entries(z):
        rel = os.path.join(*(d.split('\\') if d else []), name)
        if '-l' in sys.argv:
            print(f'{size:10d} {rel}')
            continue
        data = explode(z[off:off + packed])
        if len(data) != size:
            raise SystemExit(f'{rel}: got {len(data)} bytes, expected {size}')
        out = os.path.join(args[1], rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'wb') as f:
            f.write(data)


if __name__ == '__main__':
    main()
