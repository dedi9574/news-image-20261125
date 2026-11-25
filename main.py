#!/usr/bin/env python3
"""News front page for Wednesday 25 November 2026.

make.fun bounty news-image-20261125: sum up 25 November's world news in
one image. Renders a 1024x1024 PNG newspaper front page.

Pure Python 3 standard library only (struct, zlib, os). No network, no
randomness, no timestamps in the output: two runs produce identical bytes.

How it works:
  * A small stroke font, designed here from scratch: every glyph is a set
    of polylines on a grid (x 0..8, y -3..11; baseline y=0, cap height 10,
    x-height 7, descender -3).
  * A tiny rasterizer: filled rectangles, thick polylines, filled circles
    and polygons, plus a sky gradient, drawn into an RGB bytearray.
  * A minimal PNG encoder (filter 1 per row, zlib level 9, no ancillary
    chunks), so the file is deterministic and small.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

PAPER = (250, 247, 240)
INK = (22, 22, 22)
GREY = (96, 96, 92)
SKY_TOP = (186, 203, 211)
SKY_LOW = (233, 227, 211)
SEA = (72, 98, 118)
SEA_DARK = (52, 74, 92)
WAVE = (112, 136, 152)
CLIFF = (52, 54, 58)
HULL = (38, 42, 48)
RUST = (172, 80, 52)
SAND = (198, 164, 88)
BRIDGE = (236, 236, 232)
FIRE = (238, 122, 34)
FIRE_IN = (250, 196, 66)
SMOKE = (122, 122, 118)

# Horizontal squeeze applied to every glyph: a slightly condensed face,
# the way a newspaper sets its headlines.
COND = 0.92
# Extra space between glyphs, in grid units.
TRACK = 0.8

# ---------------------------------------------------------------------------
# Stroke font. Each entry: (advance width in grid units, [stroke, ...]).
# A stroke is a list of (x, y) points, drawn as one thick polyline.
# ---------------------------------------------------------------------------
FONT = {
    # Uppercase
    "A": (8, [[(0, 0), (4, 10), (8, 0)], [(2.5, 4), (5.5, 4)]]),
    "B": (8, [[(0, 0), (0, 10), (5, 10), (7, 8), (7, 6), (5, 5),
               (7, 4), (7, 2), (5, 0), (0, 0)]]),
    "C": (8, [[(7, 8), (5, 10), (2, 10), (0, 8), (0, 2), (2, 0),
               (5, 0), (7, 2)]]),
    "D": (8, [[(0, 0), (0, 10), (5, 10), (7, 8), (7, 2), (5, 0), (0, 0)]]),
    "E": (8, [[(7, 10), (0, 10), (0, 0), (7, 0)], [(0, 5), (5, 5)]]),
    "F": (8, [[(0, 0), (0, 10), (7, 10)], [(0, 5), (5, 5)]]),
    "G": (8, [[(7, 8), (5, 10), (2, 10), (0, 8), (0, 2), (2, 0),
               (5, 0), (7, 2), (7, 5), (4, 5)]]),
    "H": (8, [[(0, 0), (0, 10)], [(8, 0), (8, 10)], [(0, 5), (8, 5)]]),
    "I": (6, [[(1, 10), (5, 10)], [(3, 10), (3, 0)], [(1, 0), (5, 0)]]),
    "J": (7, [[(6, 10), (6, 2), (5, 0), (2, 0), (0, 2)]]),
    "K": (8, [[(0, 0), (0, 10)], [(7, 10), (0, 5), (7, 0)]]),
    "L": (8, [[(0, 10), (0, 0), (7, 0)]]),
    "M": (9, [[(0, 0), (0, 10), (4, 3), (8, 10), (8, 0)]]),
    "N": (9, [[(0, 0), (0, 10), (8, 0), (8, 10)]]),
    "O": (8, [[(2, 10), (5, 10), (7, 8), (7, 2), (5, 0), (2, 0),
               (0, 2), (0, 8), (2, 10)]]),
    "P": (8, [[(0, 0), (0, 10), (5, 10), (7, 8), (7, 6), (5, 5), (0, 5)]]),
    "Q": (8, [[(2, 10), (5, 10), (7, 8), (7, 2), (5, 0), (2, 0),
               (0, 2), (0, 8), (2, 10)], [(5, 2), (8, -1)]]),
    "R": (8, [[(0, 0), (0, 10), (5, 10), (7, 8), (7, 6), (5, 5), (0, 5)],
               [(5, 5), (8, 0)]]),
    "S": (8, [[(7, 8), (5, 10), (2, 10), (0, 8), (0, 6), (2, 5), (6, 5),
               (7, 4), (7, 2), (5, 0), (2, 0), (0, 2)]]),
    "T": (8, [[(0, 10), (8, 10)], [(4, 10), (4, 0)]]),
    "U": (8, [[(0, 10), (0, 2), (2, 0), (6, 0), (8, 2), (8, 10)]]),
    "V": (8, [[(0, 10), (4, 0), (8, 10)]]),
    "W": (10, [[(0, 10), (2, 0), (4, 5), (6, 0), (8, 10)]]),
    "X": (8, [[(0, 10), (8, 0)], [(8, 10), (0, 0)]]),
    "Y": (8, [[(0, 10), (4, 5), (8, 10)], [(4, 5), (4, 0)]]),
    "Z": (8, [[(0, 10), (8, 10), (0, 0), (8, 0)]]),
    # Lowercase
    "a": (7, [[(6, 0), (6, 7)],
               [(0, 5), (0, 2), (1, 0), (3, 0), (5, 0), (6, 1),
                (6, 6), (5, 7), (3, 7), (1, 6), (0, 5)]]),
    "b": (7, [[(0, 0), (0, 10)],
               [(0, 5), (1, 6), (3, 7), (5, 6), (6, 4), (6, 2),
                (5, 0), (3, 0), (1, 1), (0, 3)]]),
    "c": (7, [[(6, 5), (4, 7), (2, 7), (0, 5), (0, 2), (2, 0),
               (4, 0), (6, 2)]]),
    "d": (7, [[(6, 0), (6, 10)],
               [(6, 5), (5, 6), (3, 7), (1, 6), (0, 5), (0, 2),
                (1, 0), (3, 0), (5, 0), (6, 1)]]),
    "e": (7, [[(0, 3), (6, 3)],
               [(6, 3), (6, 5), (4, 7), (2, 7), (0, 5), (0, 2),
                (1, 0), (3, 0), (5, 0), (6, 2)]]),
    "f": (6, [[(3, 10), (5, 10), (6, 8), (6, 0)], [(2, 6), (6, 6)]]),
    "g": (7, [[(6, 0), (6, 7)],
               [(0, 5), (0, 2), (1, 0), (3, 0), (5, 0), (6, 1),
                (6, 6), (5, 7), (3, 7), (1, 6), (0, 5)],
               [(6, 0), (6, -2), (5, -3), (3, -3), (2, -2)]]),
    "h": (7, [[(0, 0), (0, 10)], [(0, 5), (2, 7), (4, 7), (6, 5), (6, 0)]]),
    "i": (5, [[(3, 0), (3, 7)], [(3, 9), (3, 10)]]),
    "j": (6, [[(4, 7), (4, -2), (3, -3), (1, -3)], [(4, 9), (4, 10)]]),
    "k": (7, [[(0, 0), (0, 10)], [(6, 7), (1.5, 3.5), (6, 0)]]),
    "l": (5, [[(3, 0), (3, 10)]]),
    "m": (9, [[(0, 0), (0, 7)], [(0, 5), (2, 7), (3, 7), (4, 5), (4, 0)],
               [(4, 5), (6, 7), (7, 7), (8, 5), (8, 0)]]),
    "n": (7, [[(0, 0), (0, 7)], [(0, 5), (2, 7), (4, 7), (6, 5), (6, 0)]]),
    "o": (7, [[(2, 7), (4, 7), (6, 5), (6, 2), (4, 0), (2, 0),
               (0, 2), (0, 5), (2, 7)]]),
    "p": (7, [[(0, 7), (0, -3)],
               [(0, 5), (1, 6), (3, 7), (5, 6), (6, 4), (6, 2),
                (5, 0), (3, 0), (1, 1), (0, 3)]]),
    "q": (7, [[(6, 7), (6, -3)],
               [(6, 5), (5, 6), (3, 7), (1, 6), (0, 5), (0, 2),
                (1, 0), (3, 0), (5, 0), (6, 1)]]),
    "r": (6, [[(0, 0), (0, 7)], [(0, 5), (2, 7), (4, 7), (5, 6)]]),
    "s": (7, [[(6, 6), (4, 7), (2, 7), (0, 6), (0, 4), (1, 3), (5, 3),
               (6, 2), (6, 1), (4, 0), (2, 0), (0, 1)]]),
    "t": (6, [[(3, 10), (3, 0), (5, 0)], [(1, 5), (5, 5)]]),
    "u": (7, [[(0, 7), (0, 2), (1, 0), (3, 0), (5, 0), (6, 1), (6, 7)]]),
    "v": (7, [[(0, 7), (3, 0), (6, 7)]]),
    "w": (7, [[(0, 7), (1.5, 0), (3, 3.5), (4.5, 0), (6, 7)]]),
    "x": (7, [[(0, 7), (6, 0)], [(6, 7), (0, 0)]]),
    "y": (7, [[(0, 7), (3, 0), (6, 7)], [(3, 0), (2, -3), (0, -3)]]),
    "z": (7, [[(0, 7), (6, 7), (0, 0), (6, 0)]]),
    # Digits
    "0": (8, [[(2, 10), (5, 10), (7, 8), (7, 2), (5, 0), (2, 0),
               (0, 2), (0, 8), (2, 10)]]),
    "1": (7, [[(5, 10), (3, 8), (3, 0)], [(1, 0), (5, 0)]]),
    "2": (8, [[(1, 8), (2, 10), (5, 10), (7, 8), (7, 5), (3, 2),
               (0, 0), (7, 0)]]),
    "3": (8, [[(1, 9), (3, 10), (5, 10), (7, 8), (7, 6), (5, 5),
               (7, 4), (7, 2), (5, 0), (3, 0), (1, 1)]]),
    "4": (8, [[(5, 10), (1, 4), (6, 4)], [(5, 10), (5, 0)]]),
    "5": (8, [[(7, 10), (1, 10), (1, 5), (5, 5), (7, 3), (7, 1),
               (5, 0), (2, 0), (0, 2)]]),
    "6": (8, [[(6, 9), (4, 10), (2, 9), (1, 7), (1, 3), (2, 0),
               (4, 0), (6, 1), (7, 3), (7, 5), (6, 7), (4, 7),
               (2, 6), (1, 5)]]),
    "7": (8, [[(0, 10), (7, 10), (3, 0)]]),
    "8": (8, [[(3, 10), (5, 10), (7, 8), (7, 6), (5, 5), (3, 5),
               (1, 6), (1, 8), (3, 10)],
               [(3, 5), (5, 5), (7, 4), (7, 2), (5, 0), (3, 0),
                (1, 2), (1, 4), (3, 5)]]),
    "9": (8, [[(1, 1), (3, 0), (5, 1), (6, 3), (6, 7), (5, 10),
               (3, 10), (1, 9), (0, 7), (0, 5), (1, 3), (3, 3),
               (5, 4), (6, 5)]]),
    # Punctuation and symbols
    " ": (4, []),
    ".": (4, [[(2.5, 0), (3.5, 1)]]),
    ",": (4, [[(3, 1), (3, 0), (2, -2)]]),
    ":": (4, [[(3, 7), (3, 8)], [(3, 2), (3, 3)]]),
    ";": (4, [[(3, 7), (3, 8)], [(3, 1), (3, 0), (2, -2)]]),
    "'": (4, [[(2.5, 10), (3.5, 7)]]),
    '"': (7, [[(2, 10), (2.5, 7)], [(4.5, 10), (5, 7)]]),
    "!": (4, [[(3, 10), (3, 3)], [(3, 0), (3, 1)]]),
    "?": (7, [[(1, 8), (2, 10), (4, 10), (6, 8), (6, 6), (4, 4), (3, 4)],
               [(3, 0), (3, 1)]]),
    "-": (7, [[(0, 5), (6, 5)]]),
    "\u2013": (8, [[(0, 5), (7, 5)]]),  # en dash
    "\u2014": (9, [[(0, 5), (8, 5)]]),  # em dash
    "(": (5, [[(4, 10), (2, 8), (2, 2), (4, 0)]]),
    ")": (5, [[(2, 10), (4, 8), (4, 2), (2, 0)]]),
    "%": (9, [[(0, 0), (7, 10)],
               [(1, 8), (2, 9), (3, 8), (2, 7), (1, 8)],
               [(5, 2), (6, 3), (7, 2), (6, 1), (5, 2)]]),
    "$": (8, [[(7, 8), (5, 10), (2, 10), (0, 8), (0, 6), (2, 5), (6, 5),
               (7, 4), (7, 2), (5, 0), (2, 0), (0, 2)],
               [(3.5, 11), (3.5, -1)]]),
    "&": (8, [[(6, 7), (5, 8), (3, 8), (1, 7), (1, 5), (3, 3),
               (6, 1), (7, 0)], [(1, 3), (6, 8)]]),
    "/": (7, [[(1, 0), (6, 10)]]),
    "=": (7, [[(0, 7), (6, 7)], [(0, 4), (6, 4)]]),
    "+": (7, [[(3, 1), (3, 9)], [(0, 5), (6, 5)]]),
    "\u00b7": (4, [[(2.5, 4), (3.5, 5)]]),  # middle dot
    "\u2022": (6, [[(2, 5), (3, 6), (4, 5), (3, 4), (2, 5)]]),  # bullet
}

# Fallback glyph (a hollow box) for any character missing above.
FONT["?"] = (8, [[(0, 0), (0, 10), (8, 10), (8, 0), (0, 0)],
                  [(2, 7), (3, 8), (5, 8), (6, 7), (6, 5), (4, 4), (4, 3)],
                  [(4, 0), (4, 1)]])


# ---------------------------------------------------------------------------
# Rasterizer
# ---------------------------------------------------------------------------
_DISKS = {}


def _disk_offsets(radius):
    """Pixel offsets of a filled disc of the given radius (cached)."""
    if radius not in _DISKS:
        offs = []
        for dy in range(-radius, radius + 1):
            dx_max = int((radius * radius - dy * dy) ** 0.5)
            for dx in range(-dx_max, dx_max + 1):
                offs.append((dx, dy))
        _DISKS[radius] = offs
    return _DISKS[radius]


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def fill_rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        n = len(row)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + n] = row

    def disk(self, cx, cy, r, c):
        if r <= 0:
            self._set(cx, cy, c)
            return
        for dx, dy in _disk_offsets(r):
            self._set(cx + dx, cy + dy, c)

    def line(self, x0, y0, x1, y1, w, c):
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        if x0 == x1:  # vertical: fast rectangle
            self.fill_rect(x0 - w // 2, min(y0, y1),
                           x0 - w // 2 + w, max(y0, y1) + 1, c)
            return
        if y0 == y1:  # horizontal: fast rectangle
            self.fill_rect(min(x0, x1), y0 - w // 2,
                           max(x0, x1) + 1, y0 - w // 2 + w, c)
            return
        steps = max(abs(x1 - x0), abs(y1 - y0))
        r = w // 2
        for i in range(steps + 1):
            t = i / steps
            self.disk(int(round(x0 + (x1 - x0) * t)),
                      int(round(y0 + (y1 - y0) * t)), r, c)

    def polyline(self, pts, w, c):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            self.line(ax, ay, bx, by, w, c)

    def polygon(self, pts, c):
        """Filled polygon, even-odd scanline fill."""
        ys = [int(round(y)) for _, y in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            xs.sort()
            for x0, x1 in zip(xs[::2], xs[1::2]):
                self.fill_rect(int(x0), y, int(x1) + 1, y + 1, c)

    def circle(self, cx, cy, r, c):
        """Filled circle."""
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)

    # -- text ---------------------------------------------------------------
    def text_width(self, s, size):
        sx = size / 10.0
        total = 0.0
        for ch in s:
            gw, _ = FONT.get(ch, FONT["?"])
            total += (gw + TRACK) * sx * COND
        if total:
            total -= TRACK * sx * COND
        return total

    def draw_text(self, x, y, s, size, sw, color, align="left"):
        """Draw text with its baseline at y. Returns the drawn width."""
        w = self.text_width(s, size)
        if align == "center":
            x -= w / 2.0
        elif align == "right":
            x -= w
        sx = size / 10.0
        cx = x
        for ch in s:
            gw, strokes = FONT.get(ch, FONT["?"])
            for stroke in strokes:
                pts = [(cx + px * sx * COND, y - py * sx)
                       for (px, py) in stroke]
                self.polyline(pts, sw, color)
            cx += (gw + TRACK) * sx * COND
        return w

    def wrap(self, text, size, max_w):
        """Greedy word wrap; returns a list of lines."""
        lines, cur = [], ""
        for word in text.split(" "):
            trial = word if not cur else cur + " " + word
            if self.text_width(trial, size) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def para(self, x, y, text, size, sw, color, max_w, leading):
        """Draw a wrapped paragraph; first baseline at y. Returns the
        baseline y of the line after the last one."""
        for line in self.wrap(text, size, max_w):
            self.draw_text(x, y, line, size, sw, color)
            y += leading
        return y



# ---------------------------------------------------------------------------
# Minimal deterministic PNG encoder
# ---------------------------------------------------------------------------
def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(path, cv):
    """Encode the canvas as a PNG (filter 1 on every row, zlib level 9).
    No ancillary chunks, so the bytes depend only on the pixels."""
    stride = cv.w * 3
    raw = bytearray()
    for y in range(cv.h):
        row = cv.px[y * stride:(y + 1) * stride]
        filt = bytearray(stride + 1)
        filt[0] = 1  # Sub filter
        filt[1:4] = row[0:3]
        for i in range(3, stride):
            filt[1 + i] = (row[i] - row[i - 3]) & 0xFF
        raw += filt
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    os.chmod(path, 0o644)


# ---------------------------------------------------------------------------
# Hero illustration: a Russian cargo ship burning in the Gulf of Finland
# after a Ukrainian drone strike. Everything is drawn, nothing pasted in.
# ---------------------------------------------------------------------------
def draw_scene(cv, x0, y0, x1, y1):
    horizon = y0 + int((y1 - y0) * 0.52)
    # Cold morning sky, pale at the horizon.
    for y in range(y0, horizon):
        t = (y - y0) / max(1, horizon - y0)
        c = tuple(int(SKY_TOP[i] + (SKY_LOW[i] - SKY_TOP[i]) * t)
                  for i in range(3))
        cv.fill_rect(x0, y, x1, y + 1, c)
    # Sea.
    cv.fill_rect(x0, horizon, x1, y1, SEA)
    cv.fill_rect(x0, horizon, x1, horizon + 3, SEA_DARK)
    # Wave lines, deterministic.
    for wy, wx0, wx1 in ((horizon + 14, x0 + 60, x1 - 260),
                         (horizon + 26, x0 + 200, x1 - 90),
                         (horizon + 40, x0 + 30, x1 - 420),
                         (horizon + 52, x0 + 320, x1 - 40),
                         (horizon + 64, x0 + 90, x1 - 200)):
        cv.line(wx0, wy, wx1, wy, 2, WAVE)
    # Cliffs framing the scene.
    cv.polygon([(x0, y0), (x0 + 150, y0), (x0 + 108, horizon + 6),
                (x0, horizon + 6)], CLIFF)
    cv.polygon([(x1, y0), (x1 - 120, y0), (x1 - 88, horizon + 6),
                (x1, horizon + 6)], CLIFF)
    # Gulls.
    for bx, by in ((300, y0 + 26), (700, y0 + 20), (740, y0 + 34)):
        cv.polyline([(bx, by), (bx + 6, by - 5), (bx + 12, by)], 2, INK)
    # The drone that struck: small quadcopter silhouette, upper left.
    dx, dy = x0 + 150, y0 + 38
    cv.fill_rect(dx - 7, dy - 3, dx + 8, dy + 4, INK)
    cv.line(dx - 16, dy - 6, dx + 17, dy - 6, 2, INK)
    cv.line(dx - 16, dy + 6, dx + 17, dy + 6, 2, INK)
    # Cargo ship, centre-right.
    hx0, hx1 = x0 + 400, x0 + 610
    deck = y1 - 28
    cv.polygon([(hx0, deck), (hx1, deck), (hx1 - 14, deck + 26),
                (hx0 + 16, deck + 26)], HULL)
    cv.fill_rect(hx0 + 22, deck - 24, hx0 + 76, deck, RUST)
    cv.fill_rect(hx0 + 82, deck - 28, hx0 + 136, deck, SAND)
    cv.fill_rect(hx0 + 142, deck - 20, hx0 + 176, deck, (120, 120, 110))
    # Bridge tower and mast.
    cv.fill_rect(hx1 - 42, deck - 54, hx1 - 6, deck, BRIDGE)
    cv.fill_rect(hx1 - 38, deck - 48, hx1 - 10, deck - 40, INK)
    cv.fill_rect(hx1 - 38, deck - 34, hx1 - 10, deck - 26, INK)
    cv.line(hx1 - 24, deck - 54, hx1 - 24, deck - 68, 3, INK)
    # Funnel with smoke.
    cv.fill_rect(hx0 + 4, deck - 42, hx0 + 22, deck - 24, HULL)
    for sx, sy, sr in ((hx0 + 13, deck - 52, 8), (hx0 + 8, deck - 64, 10),
                       (hx0 + 16, deck - 76, 7)):
        cv.circle(sx, sy, sr, SMOKE)
    # Explosion above the containers: starburst, hot core, black smoke.
    ex, ey = hx0 + 105, deck - 62
    star = []
    for i in range(24):
        ang = 2 * math.pi * i / 24
        r = 34 if i % 2 == 0 else 15
        star.append((ex + int(r * math.cos(ang)),
                     ey + int(r * math.sin(ang))))
    cv.polygon(star, FIRE)
    cv.circle(ex, ey, 14, FIRE_IN)
    for sx, sy, sr in ((ex - 26, ey - 26, 11), (ex + 2, ey - 34, 14),
                       (ex + 24, ey - 24, 10)):
        cv.circle(sx, sy, sr, SMOKE)
    # Frame.
    cv.fill_rect(x0, y0, x1, y0 + 2, INK)
    cv.fill_rect(x0, y1 - 2, x1, y1, INK)
    cv.fill_rect(x0, y0, x0 + 2, y1, INK)
    cv.fill_rect(x1 - 2, y0, x1, y1, INK)


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------
M = 36                      # outer margin
CW = W - 2 * M              # content width


def build_page():
    cv = Canvas(W, H, PAPER)

    # Masthead and dateline.
    cv.draw_text(W / 2, 96, "THE WORLD TODAY", 72, 8, INK, align="center")
    cv.draw_text(W / 2, 124, "WEDNESDAY, 25 NOVEMBER 2026", 21, 3, INK,
                 align="center")
    cv.fill_rect(M, 134, W - M, 137, INK)
    cv.fill_rect(M, 140, W - M, 141, INK)

    # Hero illustration and caption.
    draw_scene(cv, M, 147, W - M, 287)
    cv.draw_text(W / 2, 309,
                 "A Russian cargo ship burns in the Gulf of Finland after "
                 "a Ukrainian drone strike.",
                 15, 2, GREY, align="center")

    # Lead story.
    cv.draw_text(M, 362, "UKRAINE HITS RUSSIAN SHIP", 46, 6, INK)
    cv.draw_text(M, 412, "IN THE GULF OF FINLAND", 46, 6, INK)
    cv.para(M, 440,
            "Kyiv confirms the strike; ally Norway urges caution. Ukraine "
            "also sank a Russian naval vessel in a Libyan port.",
            19, 2, INK, CW, 24)
    cv.fill_rect(M, 478, W - M, 479, INK)

    # Six stories in a 2 x 3 grid.
    stories = [
        ("MINES HIT THREE TANKERS IN HORMUZ",
         "Iran's Revolutionary Guard Navy says three oil tankers were hit "
         "by naval mines in the Strait of Hormuz."),
        ("NVIDIA SLIDES AS TARIFF FEARS RETURN",
         "Nvidia fell 6-7% a day after surging 31.5%; the Nasdaq lost 1.5% "
         "and the S&P 500 0.5%."),
        ("GAZA STRIKE KILLS HAMAS SECURITY CHIEF",
         "An Israeli airstrike in western Gaza City killed Naeem Abu Nahel, "
         "director of Hamas' internal security apparatus."),
        ("PAKISTAN'S FIRST ASTRONAUT IN ORBIT",
         "Muhammad Zeeshan Ali launched aboard China's Shenzhou-24 to "
         "Tiangong, the first Pakistani in orbit."),
        ("HASINA TO RETURN HOME ON 16 DECEMBER",
         "Ousted prime minister Sheikh Hasina plans to return home from "
         "exile in India on 16 December, Victory Day."),
        ("HOUTHIS HIT RIYADH'S TALLEST TOWER",
         "A Houthi strike hit Riyadh's tallest tower, wounding 11; Saudi "
         "strikes killed 17 in Hodeida and 26 in Lahj."),
    ]
    col_w = (CW - 28) // 2
    row_tops = (490, 628, 766)
    for i, (head, body) in enumerate(stories):
        x = M + (i % 2) * (col_w + 28)
        y = row_tops[i // 2]
        lines = cv.wrap(head, 23, col_w)
        for j, ln in enumerate(lines[:2]):
            cv.draw_text(x, y + 23 + j * 26, ln, 23, 3, INK)
        by = y + 23 + len(lines[:2]) * 26 + 4
        for ln in cv.wrap(body, 17, col_w)[:3]:
            cv.draw_text(x, by, ln, 17, 2, INK)
            by += 20

    # Rohingya strip.
    cv.fill_rect(M, 898, W - M, 899, INK)
    cv.draw_text(M, 920, "MALAYSIA TO SEND 6,500 ROHINGYA BACK IN DECEMBER",
                 21, 3, INK)
    cv.draw_text(M, 942,
                 "Days after the World Court ruled Myanmar committed "
                 "genocide against the Rohingya.",
                 16, 2, INK)
    cv.fill_rect(M, 954, W - M, 955, INK)

    # Sport and in-brief footer.
    cv.draw_text(M, 976,
                 "SPORT  England beat Australia by eight wickets in the "
                 "second T20I.",
                 15, 2, INK)
    cv.draw_text(M, 996,
                 "ALSO  GTA 6 out since 19 Nov \u00b7 Nepal quake 5.6 "
                 "\u00b7 AIDS deaths lowest in 20+ years \u00b7 Sarkozy to trial",
                 13, 2, GREY)
    return cv


def main():
    # Write ONLY to $MAKEFUN_OUTPUT_DIR (the grader mounts the repo
    # read-only, so writing entry.png next to the script first crashes
    # the run before the output dir is ever reached). The local copy
    # next to the script is best-effort only and must never fail the run.
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "out"
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, "entry.png"), build_page())
    print("wrote %s" % os.path.join(out_dir, "entry.png"))
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        write_png(os.path.join(here, "entry.png"), build_page())
    except Exception:
        pass
    # build_page is deterministic, so both files are identical bytes.


if __name__ == "__main__":
    main()
