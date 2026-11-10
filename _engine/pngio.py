# -*- coding: utf-8 -*-
r"""pngio.py -- tiny PNG reader/writer, so the converter can run on a bare
Python install that has no Pillow.

Only what a texture converter needs:

    * read any non-interlaced PNG of colour type 0/2/3/4/6
      (grey, RGB, palette, grey+alpha, RGBA), bit depth 1/2/4/8/16
    * expose it as 8-bit RGBA
    * write 8-bit RGBA PNGs

`PNGImage` deliberately mimics the handful of Pillow calls the converter uses
(`open`, `new`, `.size`, `.convert("RGBA")`, `.getpixel`, `.putpixel`,
`.save`), so the same conversion code runs with or without Pillow.

16-bit data is reduced to its high byte; Adam7 interlacing is refused (vanilla
and every texture-pack tool writes non-interlaced PNGs).
"""
from __future__ import annotations

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"

# colour type -> samples per pixel
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PNGError(ValueError):
    pass


class PNGImage(object):
    """An 8-bit RGBA raster.  `data` is a flat bytearray, row-major."""

    __slots__ = ("width", "height", "data")

    def __init__(self, width, height, data=None):
        self.width = int(width)
        self.height = int(height)
        if data is None:
            data = bytearray(self.width * self.height * 4)
        self.data = data

    # ------------------------------------------------------------- Pillow-ish
    @property
    def size(self):
        return (self.width, self.height)

    @property
    def mode(self):
        return "RGBA"

    def convert(self, mode="RGBA"):
        if mode.upper() != "RGBA":
            raise PNGError("only RGBA is supported, not %r" % (mode,))
        return self

    def getpixel(self, xy):
        x, y = xy
        i = (y * self.width + x) * 4
        d = self.data
        return (d[i], d[i + 1], d[i + 2], d[i + 3])

    def putpixel(self, xy, colour):
        x, y = xy
        i = (y * self.width + x) * 4
        self.data[i:i + 4] = bytes((colour[0], colour[1], colour[2],
                                    colour[3] if len(colour) > 3 else 255))

    def save(self, path):
        write_png(path, self.width, self.height, self.data)

    # ------------------------------------------------------------- constructors
    @classmethod
    def new(cls, size, colour=(0, 0, 0, 0)):
        width, height = size
        rgba = bytes((colour[0], colour[1], colour[2],
                      colour[3] if len(colour) > 3 else 255))
        return cls(width, height, bytearray(rgba * (width * height)))

    @classmethod
    def load(cls, path):
        with open(path, "rb") as fh:
            return cls.from_bytes(fh.read(), path)

    @classmethod
    def from_bytes(cls, blob, path="<bytes>"):
        if not blob.startswith(SIGNATURE):
            raise PNGError("not a PNG file: %s" % path)

        pos = 8
        width = height = depth = colour_type = interlace = None
        palette = None
        trns = None
        idat = []
        while pos + 8 <= len(blob):
            (length,) = struct.unpack(">I", blob[pos:pos + 4])
            kind = blob[pos + 4:pos + 8]
            body = blob[pos + 8:pos + 8 + length]
            if len(body) != length:
                raise PNGError("truncated chunk in %s" % path)
            if kind == b"IHDR":
                (width, height, depth, colour_type,
                 _comp, _filt, interlace) = struct.unpack(">IIBBBBB", body)
            elif kind == b"PLTE":
                palette = body
            elif kind == b"tRNS":
                trns = body
            elif kind == b"IDAT":
                idat.append(body)
            elif kind == b"IEND":
                break
            pos += 12 + length

        if width is None:
            raise PNGError("no IHDR in %s" % path)
        if interlace:
            raise PNGError(
                "%s is interlaced (Adam7); re-save it as a normal PNG" % path)
        if colour_type not in CHANNELS:
            raise PNGError("unknown colour type %d in %s" % (colour_type, path))
        if colour_type == 3 and palette is None:
            raise PNGError("palette image without PLTE: %s" % path)

        raw = zlib.decompress(b"".join(idat))
        rows = _unfilter(raw, width, height, depth, colour_type)
        return cls._from_samples(rows, width, height, depth, colour_type,
                                 palette, trns, path)

    # --------------------------------------------------------------- internals
    @classmethod
    def _from_samples(cls, rows, width, height, depth, colour_type,
                      palette, trns, path):
        channels = CHANNELS[colour_type]
        bits = depth * channels
        stride = (width * bits + 7) // 8
        out = bytearray(width * height * 4)

        # transparency keys for grey / RGB images
        key = None
        if trns is not None and colour_type == 0:
            key = (struct.unpack(">H", trns[:2])[0],)
        elif trns is not None and colour_type == 2:
            key = struct.unpack(">HHH", trns[:6])
        alphas = trns if (trns is not None and colour_type == 3) else b""

        if depth == 8:
            for y in range(height):
                base = y * stride
                o = y * width * 4
                for x in range(width):
                    p = base + x * channels
                    if colour_type == 0:
                        v = rows[p]
                        rgba = (v, v, v, 0 if key == (v,) else 255)
                    elif colour_type == 2:
                        r, g, b = rows[p], rows[p + 1], rows[p + 2]
                        rgba = (r, g, b,
                                0 if key == (r, g, b) else 255)
                    elif colour_type == 3:
                        idx = rows[p]
                        q = idx * 3
                        a = alphas[idx] if idx < len(alphas) else 255
                        rgba = (palette[q], palette[q + 1], palette[q + 2], a)
                    elif colour_type == 4:
                        v, a = rows[p], rows[p + 1]
                        rgba = (v, v, v, a)
                    else:                                  # colour type 6
                        rgba = (rows[p], rows[p + 1], rows[p + 2], rows[p + 3])
                    out[o:o + 4] = bytes(rgba)
                    o += 4

        elif depth == 16:
            for y in range(height):
                base = y * stride
                o = y * width * 4
                for x in range(width):
                    p = base + x * channels * 2
                    if colour_type == 0:
                        hi, lo = rows[p], rows[p + 1]
                        v = (hi << 8) | lo
                        rgba = (hi, hi, hi, 0 if key == (v,) else 255)
                    elif colour_type == 2:
                        r = (rows[p] << 8) | rows[p + 1]
                        g = (rows[p + 2] << 8) | rows[p + 3]
                        b = (rows[p + 4] << 8) | rows[p + 5]
                        rgba = (r >> 8, g >> 8, b >> 8,
                                0 if key == (r, g, b) else 255)
                    elif colour_type == 4:
                        v = rows[p]
                        rgba = (v, v, v, rows[p + 2])
                    else:
                        rgba = (rows[p], rows[p + 2], rows[p + 4], rows[p + 6])
                    out[o:o + 4] = bytes(rgba)
                    o += 4

        else:                                              # depth 1, 2 or 4
            per_byte = 8 // depth
            mask = (1 << depth) - 1
            scale = 255 // mask
            for y in range(height):
                base = y * stride
                o = y * width * 4
                for x in range(width):
                    p = base + x // per_byte
                    shift = 8 - depth * (x % per_byte + 1)
                    v = (rows[p] >> shift) & mask
                    if colour_type == 3:
                        q = v * 3
                        if q + 2 >= len(palette):
                            raise PNGError("palette index out of range in %s"
                                           % path)
                        a = alphas[v] if v < len(alphas) else 255
                        rgba = (palette[q], palette[q + 1], palette[q + 2], a)
                    else:                                  # grey 1/2/4 bit
                        g = v * scale
                        rgba = (g, g, g, 0 if key == (v,) else 255)
                    out[o:o + 4] = bytes(rgba)
                    o += 4
        return cls(width, height, out)


def _unfilter(raw, width, height, depth, colour_type):
    channels = CHANNELS[colour_type]
    bits = depth * channels
    bpp = max(1, (bits + 7) // 8)
    stride = (width * bits + 7) // 8
    need = height * (stride + 1)
    if len(raw) < need:
        raise PNGError("image data is shorter than the header says")
    out = bytearray(height * stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:                                   # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:                                   # Up
            if y:
                base = (y - 1) * stride
                for i in range(stride):
                    line[i] = (line[i] + out[base + i]) & 0xFF
        elif ftype == 3:                                   # Average
            base = (y - 1) * stride
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = out[base + i] if y else 0
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
        elif ftype == 4:                                   # Paeth
            base = (y - 1) * stride
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = out[base + i] if y else 0
                c = out[base + i - bpp] if (y and i >= bpp) else 0
                p = a + b - c
                pa = p - a if p > a else a - p
                pb = p - b if p > b else b - p
                pc = p - c if p > c else c - p
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                line[i] = (line[i] + pred) & 0xFF
        else:
            raise PNGError("unknown filter type %d" % ftype)
        out[y * stride:(y + 1) * stride] = line
    return out


def _chunk(kind, body):
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def write_png(path, width, height, rgba):
    """Write an 8-bit RGBA PNG."""
    rgba = bytes(rgba)
    stride = width * 4
    raw = bytearray(height * (stride + 1))
    for y in range(height):
        base = y * (stride + 1)
        raw[base] = 0                                       # filter: none
        raw[base + 1:base + 1 + stride] = rgba[y * stride:(y + 1) * stride]
    body = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    with open(path, "wb") as fh:
        fh.write(SIGNATURE)
        fh.write(_chunk(b"IHDR", ihdr))
        fh.write(_chunk(b"IDAT", body))
        fh.write(_chunk(b"IEND", b""))


# ------------------------------------------------------------------ shortcuts
def open_rgba(path):
    return PNGImage.load(path)
