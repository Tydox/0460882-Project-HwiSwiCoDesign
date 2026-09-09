#!/usr/bin/env python
"""
Optimized pure-Python DEFLATE (gzip) and bzip2 decoder.
Original implementation: Copyright 2006--2007-01-21 Paul Sladen
http://www.paul.sladen.org/projects/compression/
"""

import hashlib
import os
import struct
import pyperf

int2byte = struct.Struct(">B").pack


class BitfieldBase(object):

    def __init__(self, x):
        if isinstance(x, BitfieldBase):
            self.f = x.f
            self.bits = x.bits
            self.bitfield = x.bitfield
            self.count = x.count
        else:
            self.f = x
            self.bits = 0
            self.bitfield = 0x0
            self.count = 0

    def _read(self, n):
        s = self.f.read(n)
        if not s:
            raise EOFError("Unexpected end of input stream")
        self.count += len(s)
        return s

    def needbits(self, n):
        while self.bits < n:
            self._more()

    @staticmethod
    def _mask(n):
        return (1 << n) - 1

    def toskip(self):
        return self.bits & 0x7

    def align(self):
        self.readbits(self.toskip())

    def dropbits(self, n=8):
        while n >= self.bits and n > 7:
            n -= self.bits
            self.bits = 0
            n -= len(self.f.read(n >> 3)) << 3
        if n:
            self.readbits(n)

    def dropbytes(self, n=1):
        self.dropbits(n << 3)

    def tell(self):
        return self.count - ((self.bits + 7) >> 3), 7 - ((self.bits - 1) & 0x7)

    def tellbits(self):
        byte_pos, bit_pos = self.tell()
        return (byte_pos << 3) + bit_pos


class Bitfield(BitfieldBase):

    def _more(self):
        c = self._read(1)
        self.bitfield += c[0] << self.bits
        self.bits += 8

    def snoopbits(self, n=8):
        if n > self.bits:
            self.needbits(n)
        return self.bitfield & ((1 << n) - 1)

    def readbits(self, n=8):
        if n > self.bits:
            self.needbits(n)
        r = self.bitfield & ((1 << n) - 1)
        self.bits -= n
        self.bitfield >>= n
        return r


class RBitfield(BitfieldBase):

    def _more(self):
        c = self._read(1)
        self.bitfield = (self.bitfield << 8) + c[0]
        self.bits += 8

    def snoopbits(self, n=8):
        if n > self.bits:
            self.needbits(n)
        return (self.bitfield >> (self.bits - n)) & ((1 << n) - 1)

    def readbits(self, n=8):
        if n > self.bits:
            self.needbits(n)
        r = (self.bitfield >> (self.bits - n)) & ((1 << n) - 1)
        self.bits -= n
        self.bitfield &= (1 << self.bits) - 1
        return r


def printbits(v, n):
    o = ''
    for _ in range(n):
        o = ('1' if v & 1 else '0') + o
        v >>= 1
    return o


class HuffmanLength(object):

    def __init__(self, code, bits=0):
        self.code = code
        self.bits = bits
        self.symbol = None
        self.reverse_symbol = None

    def __repr__(self):
        return repr((self.code, self.bits, self.symbol, self.reverse_symbol))

    @staticmethod
    def _sort_func(obj):
        return (obj.bits, obj.code)


def reverse_bits(v, n):
    z = 0
    for _ in range(n):
        z = (z << 1) | (v & 1)
        v >>= 1
    return z


def reverse_bytes(v, n):
    a = 0xff << 0
    b = 0xff << (n - 8)
    z = 0
    for i in range(n - 8, -8, -16):
        z |= (v >> i) & a
        z |= (v << i) & b
        a <<= 8
        b >>= 8
    return z


class HuffmanTable(object):

    def __init__(self, bootstrap):
        table_list = []
        start, bits = bootstrap[0]
        for finish, endbits in bootstrap[1:]:
            if bits:
                for code in range(start, finish):
                    table_list.append(HuffmanLength(code, bits))
            start, bits = finish, endbits
            if endbits == -1:
                break
        table_list.sort(key=HuffmanLength._sort_func)
        self.table = table_list

        self.lookup_normal = {}
        self.lookup_reversed = {}
        self.unique_lengths = []

    def populate_huffman_symbols(self):
        bits, symbol = -1, -1
        for x in self.table:
            symbol += 1
            if x.bits != bits:
                symbol <<= (x.bits - bits)
                bits = x.bits
            x.symbol = symbol
            x.reverse_symbol = reverse_bits(symbol, bits)

        self.lookup_normal = {(x.bits, x.symbol): x.code for x in self.table}
        self.lookup_reversed = {(x.bits, x.reverse_symbol): x.code for x in self.table}
        self.unique_lengths = sorted(list(set(x.bits for x in self.table if x.bits > 0)))

    def tables_by_bits(self):
        d = {}
        for x in self.table:
            d.setdefault(x.bits, []).append(x)
        return d

    def min_max_bits(self):
        if self.table:
            self.min_bits = min(x.bits for x in self.table if x.bits > 0)
            self.max_bits = max(x.bits for x in self.table)
        else:
            self.min_bits, self.max_bits = 0, 0

    def find_next_symbol(self, field, reversed_code=True):
        lookup = self.lookup_reversed if reversed_code else self.lookup_normal
        for length in self.unique_lengths:
            cached = field.snoopbits(length)
            code = lookup.get((length, cached))
            if code is not None:
                field.readbits(length)
                return code

        raise Exception(f"Unfound symbol @ bit pos {field.tellbits()}")


class OrderedHuffmanTable(HuffmanTable):

    def __init__(self, lengths):
        table_len = len(lengths)
        z = list(zip(range(table_len), lengths)) + [(table_len, -1)]
        HuffmanTable.__init__(self, z)


def code_length_orders(i):
    return (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3,
            13, 2, 14, 1, 15)[i]


def distance_base(i):
    return (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
            257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193,
            12289, 16385, 24577)[i]


def length_base(i):
    return (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35,
            43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258)[i - 257]


def extra_distance_bits(n):
    if 0 <= n <= 1:
        return 0
    elif 2 <= n <= 29:
        return (n >> 1) - 1
    raise Exception(f"Illegal distance code: {n}")


def extra_length_bits(n):
    if 257 <= n <= 260 or n == 285:
        return 0
    elif 261 <= n <= 284:
        return ((n - 257) >> 2) - 1
    raise Exception(f"Illegal length code: {n}")


def move_to_front(lst, c):
    val = lst.pop(c)
    lst.insert(0, val)


def bwt_transform(l_seq):
    counts = [0] * 257
    for byte_val in l_seq:
        counts[byte_val + 1] += 1

    for i in range(1, 256):
        counts[i] += counts[i - 1]

    base = counts[:256]

    pointers = [-1] * len(l_seq)
    for i, symbol in enumerate(l_seq):
        pointers[base[symbol]] = i
        base[symbol] += 1
    return pointers


def bwt_reverse(l_seq, end):
    if not l_seq:
        return b""
    t_table = bwt_transform(l_seq)
    out = bytearray(len(l_seq))
    curr = end
    for i in range(len(l_seq)):
        curr = t_table[curr]
        out[i] = l_seq[curr]
    return bytes(out)


def compute_used(b):
    huffman_used_map = b.readbits(16)
    used = []
    for i in range(15, -1, -1):
        if huffman_used_map & (1 << i):
            bitmap = b.readbits(16)
            for j in range(15, -1, -1):
                used.append(bool(bitmap & (1 << j)))
        else:
            used.extend([False] * 16)
    return used


def compute_selectors_list(b, huffman_groups):
    selectors_used = b.readbits(15)
    mtf = list(range(huffman_groups))
    selectors_list = []
    for _ in range(selectors_used):
        c = 0
        while b.readbits(1):
            c += 1
            if c >= huffman_groups:
                raise Exception("Bzip2 chosen selector greater than number of groups")
        move_to_front(mtf, c)
        selectors_list.append(mtf[0])
    return selectors_list


def compute_tables(b, huffman_groups, symbols_in_use):
    groups_lengths = []
    for _ in range(huffman_groups):
        length = b.readbits(5)
        lengths = []
        for _ in range(symbols_in_use):
            if not 0 <= length <= 20:
                raise Exception("Bzip2 Huffman length code outside range 0..20")
            while b.readbits(1):
                length -= (b.readbits(1) * 2) - 1
            lengths.append(length)
        groups_lengths.append(lengths)

    tables = []
    for g in groups_lengths:
        codes = OrderedHuffmanTable(g)
        codes.populate_huffman_symbols()
        codes.min_max_bits()
        tables.append(codes)
    return tables


def decode_huffman_block(b, out):
    randomised = b.readbits(1)
    if randomised:
        raise Exception("Bzip2 randomised support not implemented")
    pointer = b.readbits(24)
    used = compute_used(b)

    huffman_groups = b.readbits(3)
    if not 2 <= huffman_groups <= 6:
        raise Exception("Bzip2: Number of Huffman groups not in range 2..6")

    selectors_list = compute_selectors_list(b, huffman_groups)
    symbols_in_use = sum(used) + 2
    tables = compute_tables(b, huffman_groups, symbols_in_use)

    favourites = [i for i, x in enumerate(used) if x]

    selector_pointer = 0
    decoded = 0
    repeat = repeat_power = 0
    buffer = bytearray()
    t = None

    while True:
        decoded -= 1
        if decoded <= 0:
            decoded = 50
            if selector_pointer < len(selectors_list):
                t = tables[selectors_list[selector_pointer]]
                selector_pointer += 1

        r = t.find_next_symbol(b, False)
        if 0 <= r <= 1:
            if repeat == 0:
                repeat_power = 1
            repeat += repeat_power << r
            repeat_power <<= 1
            continue
        elif repeat > 0:
            buffer.extend(bytes([favourites[0]]) * repeat)
            repeat = 0

        if r == symbols_in_use - 1:
            break
        else:
            val = favourites.pop(r - 1)
            favourites.insert(0, val)
            buffer.append(val)

    nt = bwt_reverse(buffer, pointer)
    i = 0
    nt_len = len(nt)
    while i < nt_len:
        if i < nt_len - 4 and nt[i] == nt[i + 1] == nt[i + 2] == nt[i + 3]:
            count = nt[i + 4] + 4
            out.extend(bytes([nt[i]]) * count)
            i += 5
        else:
            out.append(nt[i])
            i += 1


def bzip2_main(input_stream):
    b = RBitfield(input_stream)
    method = b.readbits(8)
    if method != ord('h'):
        raise Exception("Unknown compression method")

    blocksize = b.readbits(8)
    if not (ord('1') <= blocksize <= ord('9')):
        raise Exception("Unknown Bzip2 blocksize")

    out = bytearray()
    while True:
        blocktype = b.readbits(48)
        b.readbits(32)  # CRC
        if blocktype == 0x314159265359:
            decode_huffman_block(b, out)
        elif blocktype == 0x177245385090:
            b.align()
            break
        else:
            raise Exception("Illegal Bzip2 blocktype")
    return bytes(out)


def gzip_main(field):
    b = Bitfield(field)
    method = b.readbits(8)
    if method != 8:
        raise Exception("Unknown compression method")

    flags = b.readbits(8)
    b.readbits(32)  # mtime
    b.readbits(8)   # extra_flags
    b.readbits(8)   # os_type

    if flags & 0x04:
        xlen = b.readbits(16)
        b.dropbytes(xlen)
    while flags & 0x08:
        if not b.readbits(8):
            break
    while flags & 0x10:
        if not b.readbits(8):
            break
    if flags & 0x02:
        b.readbits(16)

    out = bytearray()
    while True:
        lastbit = b.readbits(1)
        blocktype = b.readbits(2)

        if blocktype == 0:
            b.align()
            length = b.readbits(16)
            if length & b.readbits(16):
                raise Exception("Stored block lengths do not match each other")
            for _ in range(length):
                out.append(b.readbits(8))

        elif blocktype in (1, 2):
            if blocktype == 1:
                static_huffman_bootstrap = [
                    (0, 8), (144, 9), (256, 7), (280, 8), (288, -1)]
                static_huffman_lengths_bootstrap = [(0, 5), (32, -1)]
                main_literals = HuffmanTable(static_huffman_bootstrap)
                main_distances = HuffmanTable(static_huffman_lengths_bootstrap)
            else:
                literals = b.readbits(5) + 257
                distances = b.readbits(5) + 1
                code_lengths_length = b.readbits(4) + 4

                code_lens = [0] * 19
                for i in range(code_lengths_length):
                    code_lens[code_length_orders(i)] = b.readbits(3)

                dynamic_codes = OrderedHuffmanTable(code_lens)
                dynamic_codes.populate_huffman_symbols()
                dynamic_codes.min_max_bits()

                code_lengths = []
                n = 0
                target_total = literals + distances
                while n < target_total:
                    r = dynamic_codes.find_next_symbol(b)
                    if 0 <= r <= 15:
                        count = 1
                        what = r
                    elif r == 16:
                        count = 3 + b.readbits(2)
                        what = code_lengths[-1]
                    elif r == 17:
                        count = 3 + b.readbits(3)
                        what = 0
                    elif r == 18:
                        count = 11 + b.readbits(7)
                        what = 0
                    else:
                        raise Exception("Code length out of range")
                    code_lengths.extend([what] * count)
                    n += count

                main_literals = OrderedHuffmanTable(code_lengths[:literals])
                main_distances = OrderedHuffmanTable(code_lengths[literals:])

            main_literals.populate_huffman_symbols()
            main_distances.populate_huffman_symbols()
            main_literals.min_max_bits()
            main_distances.min_max_bits()

            while True:
                r = main_literals.find_next_symbol(b)
                if 0 <= r <= 255:
                    out.append(r)
                elif r == 256:
                    break
                elif 257 <= r <= 285:
                    length_extra = b.readbits(extra_length_bits(r))
                    length = length_base(r) + length_extra

                    r1 = main_distances.find_next_symbol(b)
                    if 0 <= r1 <= 29:
                        distance = distance_base(r1) + b.readbits(extra_distance_bits(r1))
                        while length > distance:
                            out.extend(out[-distance:])
                            length -= distance
                        out.extend(out[-distance:-distance + length] if length < distance else out[-distance:])
                    else:
                        raise Exception("Illegal distance symbol")
                else:
                    raise Exception("Illegal literal/length symbol")
        elif blocktype == 3:
            raise Exception("Illegal unused blocktype")

        if lastbit:
            break

    b.align()
    b.readbits(32)  # CRC
    b.readbits(32)  # ISIZE
    return bytes(out)


def bench_pyflake(loops, filename):
    input_fp = open(filename, 'rb')
    range_it = range(loops)
    t0 = pyperf.perf_counter()

    for _ in range_it:
        input_fp.seek(0)
        field = RBitfield(input_fp)

        magic = field.readbits(16)
        if magic == 0x1f8b:
            out = gzip_main(field)
        elif magic == 0x425a:
            out = bzip2_main(field)
        else:
            raise Exception(f"Unknown file magic {hex(magic)}")

    dt = pyperf.perf_counter() - t0
    input_fp.close()

    if hashlib.md5(out).hexdigest() != "afa004a630fe072901b1d9628b960974":
        raise Exception("MD5 checksum mismatch")

    return dt


if __name__ == '__main__':
    runner = pyperf.Runner()
    runner.metadata['description'] = "Pyflate benchmark"

    filename = os.path.join(os.path.dirname(__file__),
                            "data", "interpreter.tar.bz2")
    runner.bench_time_func('pyflate', bench_pyflake, filename)
