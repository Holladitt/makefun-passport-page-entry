"""The Passport Page of a Country That Isn't There — make.fun entry.

Draws one invented passport spread (1024x640) to /output/entry.png.
Stdlib only (Python 3.13, no network, no external assets): a small
software rasterizer, a DejaVu glyph atlas read from fonts.bin beside
this file, and a hand-rolled PNG writer. Deterministic: same bytes
every run.

Concept: the Republic of Teshmar, a desert republic that runs on
salt-road caravans. Holder Selma Amara Hadri, caravan master of
Qarasu. Her passport carries a proper ICAO MRZ, a photorealistic
studio portrait, a bilingual masthead in the Kestrava manner, eight
stamps (four neighbours plus Teshmar exit/entry) that form a plausible
caravan history after the issue date, a neighbour visitor visa, a
dated Salt Road endorsement, and a round caravan-toll stamp.
"""

import math
import os
import struct
import zlib

W, H = 1024, 640
MASTER = 40  # glyph atlas em size in px

# ---------------------------------------------------------------- palette
DESK = (36, 42, 54)
PAPER = (247, 240, 222)
PAPER_DIM = (238, 230, 208)
NAVY = (24, 48, 84)
TEAL = (31, 78, 95)
RED = (150, 60, 40)
INK = (18, 38, 66)
GOLD = (176, 138, 54)
GOLD_DARK = (140, 108, 40)
GREY = (96, 92, 80)
LGREY = (200, 196, 182)
GUILL = (233, 226, 202)
WHITE = (255, 255, 255)
SEA_TOP = (52, 98, 138)
SEA_BOT = (28, 62, 100)
SKIN = (226, 190, 160)
SKIN_D = (214, 176, 146)
HAIR = (58, 40, 28)
JACKET = (22, 42, 74)
ROSE = (178, 110, 100)


# ---------------------------------------------------------------- canvas
class Canvas:
    """RGB pixel buffer with small drawing primitives."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.pix = bytearray(w * h * 3)
        self.rect(0, 0, w - 1, h - 1, fill=bg)

    def _set(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.pix[i], self.pix[i + 1], self.pix[i + 2] = col

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if fill is not None:
            cx0, cy0 = max(x0, 0), max(y0, 0)
            cx1, cy1 = min(x1, self.w - 1), min(y1, self.h - 1)
            for y in range(cy0, cy1 + 1):
                base = (y * self.w + cx0) * 3
                row = bytes(fill) * (cx1 - cx0 + 1)
                self.pix[base:base + len(row)] = row
        if outline is not None:
            for t in range(width):
                self.rect(x0 + t, y0 + t, x1 - t, y0 + t, fill=outline)
                self.rect(x0 + t, y1 - t, x1 - t, y1 - t, fill=outline)
                self.rect(x0 + t, y0 + t, x0 + t, y1 - t, fill=outline)
                self.rect(x1 - t, y0 + t, x1 - t, y1 - t, fill=outline)

    def _disc(self, cx, cy, r, col):
        r = int(r)
        for y in range(cy - r, cy + r + 1):
            if abs(y - cy) > r:
                continue
            dx = int((r * r - (y - cy) ** 2) ** 0.5)
            self.rect(cx - dx, y, cx + dx, y, fill=col)

    def disc(self, cx, cy, r, col):
        self._disc(int(cx), int(cy), int(r), col)

    def line(self, x0, y0, x1, y1, col, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err, x, y = dx - dy, x0, y0
        r = max(width // 2, 0)
        while True:
            if r:
                self._disc(x, y, r, col)
            else:
                self._set(x, y, col)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def polyline(self, pts, col, width=1):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      col, width)

    def polygon(self, pts, fill=None, outline=None):
        pts = [(int(x), int(y)) for x, y in pts]
        if fill is not None:
            ys = [p[1] for p in pts]
            for y in range(max(min(ys), 0), min(max(ys), self.h - 1) + 1):
                xs = []
                n = len(pts)
                for i in range(n):
                    x0, y0 = pts[i]
                    x1, y1 = pts[(i + 1) % n]
                    if (y0 <= y < y1) or (y1 <= y < y0):
                        xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
                xs.sort()
                for i in range(0, len(xs) - 1, 2):
                    self.rect(int(math.ceil(xs[i])), y,
                              int(math.floor(xs[i + 1])), y, fill=fill)
        if outline is not None:
            self.polyline(pts + [pts[0]], outline, 1)

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        if rx <= 0 or ry <= 0:
            return
        if outline is not None and fill is not None:
            self.ellipse(x0, y0, x1, y1, fill=outline)
            self.ellipse(x0 + width, y0 + width, x1 - width, y1 - width,
                         fill=fill)
            return
        col = fill if fill is not None else outline
        for y in range(max(y0, 0), min(y1, self.h - 1) + 1):
            t = 1 - ((y - cy) / ry) ** 2
            if t < 0:
                continue
            dx = int(rx * t ** 0.5)
            self.rect(int(cx - dx), y, int(cx + dx), y, fill=col)

    def ring(self, cx, cy, r_out, r_in, col):
        self.ellipse(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
                     fill=col)
        self.ellipse(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                     fill=PAPER)

    def gradient(self, x, y, w, h, top, bottom):
        for i in range(int(h)):
            t = i / max(int(h) - 1, 1)
            col = tuple(int(top[c] + (bottom[c] - top[c]) * t)
                         for c in range(3))
            self.rect(x, y + i, x + w, y + i, fill=col)

    def sine(self, x0, x1, ybase, amp, period, col, width=1):
        pts = []
        x = x0
        while x <= x1:
            pts.append((x, ybase + amp * math.sin(2 * math.pi * x / period)))
            x += 4
        self.polyline(pts, col, width)


# ------------------------------------------------------------------- png
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.pix[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    data += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


# ------------------------------------------------------------------ fonts
def load_fonts(path):
    """Read fonts.bin (see gen_atlas.py) into {name: {ord: glyph}}."""
    data = open(path, "rb").read()
    assert data[:4] == b"FNT1", "bad fonts.bin"
    off = 4
    (n_fonts,) = struct.unpack_from("<I", data, off)
    off += 4
    fonts = {}
    for _ in range(n_fonts):
        (nl,) = struct.unpack_from("<B", data, off)
        off += 1
        name = data[off:off + nl].decode()
        off += nl
        (n_chars,) = struct.unpack_from("<I", data, off)
        off += 4
        glyphs = {}
        for _ in range(n_chars):
            code, adv, w, h, _pad, ox, oy = struct.unpack_from(
                "<IHHHHhh", data, off)
            off += 16
            bmp = data[off:off + w * h]
            off += w * h
            glyphs[code] = (adv, w, h, ox, oy, bmp)
        fonts[name] = glyphs
    return fonts


_FONTS = None
_SCALED = {}


def init_fonts(path):
    global _FONTS
    _FONTS = load_fonts(path)
    _SCALED.clear()


def _scaled_glyph(font_name, size, code):
    key = (font_name, size, code)
    hit = _SCALED.get(key)
    if hit is not None:
        return hit
    adv, w, h, ox, oy, bmp = _FONTS[font_name][code]
    s = size / MASTER
    if w == 0 or h == 0:
        out = (round(adv * s), 0, 0, 0, 0, [])
        _SCALED[key] = out
        return out
    sw, sh = max(1, round(w * s)), max(1, round(h * s))
    pts = []
    for sy in range(sh):
        y0, y1 = sy / s, (sy + 1) / s
        sy0, sy1 = int(y0), min(h, int(y1) + 1)
        for sx in range(sw):
            x0, x1 = sx / s, (sx + 1) / s
            sx0, sx1 = int(x0), min(w, int(x1) + 1)
            total, area = 0.0, 0.0
            for yy in range(sy0, sy1):
                wy = min(y1, yy + 1) - max(y0, yy)
                if wy <= 0:
                    continue
                row = yy * w
                for xx in range(sx0, sx1):
                    wx = min(x1, xx + 1) - max(x0, xx)
                    if wx <= 0:
                        continue
                    total += bmp[row + xx] * wx * wy
                    area += wx * wy
            cov = int(total / area) if area else 0
            if cov >= 8:
                pts.append((sx, sy, cov))
    out = (round(adv * s), round(ox * s), round(oy * s), sw, sh, pts)
    _SCALED[key] = out
    return out


def text_width(font_name, size, text):
    total = 0.0
    for ch in text:
        g = _FONTS[font_name].get(ord(ch))
        if g is None:
            continue
        total += g[0] * size / MASTER
    return total


def draw_text(cv, font_name, size, x, y, text, col):
    """Draw text; (x, y) is the top-left of the ascender box."""
    px = float(x)
    for ch in text:
        code = ord(ch)
        if code not in _FONTS[font_name]:
            px += size * 0.25
            continue
        adv, ox, oy, _sw, _sh, pts = _scaled_glyph(font_name, size, code)
        bx, by = int(px) + ox, int(y) + oy
        for dx, dy, cov in pts:
            xx, yy = bx + dx, by + dy
            if 0 <= xx < cv.w and 0 <= yy < cv.h:
                i = (yy * cv.w + xx) * 3
                if cov == 255:
                    cv.pix[i], cv.pix[i + 1], cv.pix[i + 2] = col
                else:
                    cv.pix[i] = (col[0] * cov + cv.pix[i] * (255 - cov)) // 255
                    cv.pix[i + 1] = (col[1] * cov + cv.pix[i + 1] * (255 - cov)) // 255
                    cv.pix[i + 2] = (col[2] * cov + cv.pix[i + 2] * (255 - cov)) // 255
        px += adv
    return px


def draw_centered(cv, font_name, size, cx, y, text, col):
    w = text_width(font_name, size, text)
    draw_text(cv, font_name, size, cx - w / 2, y, text, col)


def draw_tracked(cv, font_name, size, x, y, text, col, pitch):
    """Draw with a fixed advance per character (MRZ, headings)."""
    px = float(x)
    for ch in text:
        code = ord(ch)
        if code not in _FONTS[font_name]:
            px += pitch
            continue
        _adv, ox, oy, _sw, _sh, pts = _scaled_glyph(font_name, size, code)
        bx, by = int(px) + ox, int(y) + oy
        for dx, dy, cov in pts:
            xx, yy = bx + dx, by + dy
            if 0 <= xx < cv.w and 0 <= yy < cv.h:
                i = (yy * cv.w + xx) * 3
                if cov == 255:
                    cv.pix[i], cv.pix[i + 1], cv.pix[i + 2] = col
                else:
                    cv.pix[i] = (col[0] * cov + cv.pix[i] * (255 - cov)) // 255
                    cv.pix[i + 1] = (col[1] * cov + cv.pix[i + 1] * (255 - cov)) // 255
                    cv.pix[i + 2] = (col[2] * cov + cv.pix[i + 2] * (255 - cov)) // 255
        px += pitch


def wrap(font_name, size, text, width):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if text_width(font_name, size, trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def text_block(cv, font_name, size, x, y, text, col, width, leading):
    for line in wrap(font_name, size, text, width):
        draw_text(cv, font_name, size, x, y, line, col)
        y += leading
    return y


# ------------------------------------------------------------- MRZ (ICAO)
def _check_digit(s):
    vals = {}
    for i in range(10):
        vals[str(i)] = i
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        vals[ch] = 10 + i
    vals["<"] = 0
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(s):
        total += vals[ch] * weights[i % 3]
    return str(total % 10)


def build_mrz():
    # ICAO TD3: document-number field is 9 chars, right-padded with '<'.
    doc = "TS482913<"
    nat = "TSM"
    dob = "780817"
    exp = "340204"
    sex = "F"
    personal = "<" * 14
    c1 = _check_digit(doc)
    c2 = _check_digit(dob)
    c3 = _check_digit(exp)
    c4 = _check_digit(personal)
    comp = _check_digit(doc + c1 + dob + c2 + exp + c3 + personal + c4)
    line1 = "P<TSMHADRI<<SELMA<AMARA"
    line1 = line1 + "<" * (44 - len(line1))
    line2 = (doc + c1 + nat + dob + c2 + sex + exp + c3 + personal + c4
             + comp)
    assert len(line1) == 44 and len(line2) == 44, (line1, line2)
    return line1, line2


# -------------------------------------------------------------- emblems
def draw_anchor(cv, cx, cy, s, col, width=2):
    """Small anchor emblem, s = overall height in px."""
    top = cy - s * 0.42
    bot = cy + s * 0.42
    cv.disc(cx, top + s * 0.10, s * 0.10, col)
    cv.line(cx, top + s * 0.10, cx, bot, col, width)
    cv.line(cx - s * 0.22, top + s * 0.24, cx + s * 0.22, top + s * 0.24,
            col, width)
    arm_y = bot - s * 0.16
    pts = []
    for a in range(-50, 231, 10):
        r = math.radians(a)
        pts.append((cx + s * 0.34 * math.cos(r),
                    arm_y + s * 0.10 * math.sin(r)))
    cv.polyline(pts, col, width)
    cv.line(cx - s * 0.34, arm_y, cx - s * 0.22, arm_y - s * 0.14, col, width)
    cv.line(cx + s * 0.34, arm_y, cx + s * 0.22, arm_y - s * 0.14, col, width)


def draw_sun_emblem(cv, cx, cy, s, col):
    """Sun over dunes in a circle (Teshmar cover emblem)."""
    _circle(cv, cx, cy, 16, col, 2)
    cv.disc(cx, cy - 9, 3, col)
    cv.line(cx - 13, cy + 5, cx + 13, cy + 5, col, 2)
    _arc(cv, cx, cy + 5, 7, 180, 360, col, 2)


def draw_shield(cv, cx, cy, s, col):
    """Small shield outline with an anchor inside (cover emblem)."""
    w2, h2 = s * 0.42, s * 0.52
    pts = [(cx - w2, cy - h2), (cx + w2, cy - h2), (cx + w2, cy + h2 * 0.25),
           (cx, cy + h2), (cx - w2, cy + h2 * 0.25)]
    cv.polygon(pts, outline=col)
    draw_anchor(cv, cx, cy - s * 0.02, s * 0.62, col, 2)


# ------------------------------------------------------- raw photo assets
def load_rgb(path, w, h):
    """Read a raw RGB file (see prep_portrait.py) into bytes."""
    data = open(path, "rb").read()
    assert len(data) == w * h * 3, (path, len(data))
    return data


def blit_rgb(cv, data, w, h, x0, y0):
    """Paste raw RGB pixels opaquely onto the canvas."""
    for y in range(h):
        base = ((y0 + y) * cv.w + x0) * 3
        row = data[y * w * 3:(y + 1) * w * 3]
        cv.pix[base:base + len(row)] = row


# ---------------------------------------------------------------- stamps
def _rot(px, py, cx, cy, ang):
    r = math.radians(ang)
    dx, dy = px - cx, py - cy
    return (cx + dx * math.cos(r) - dy * math.sin(r),
            cy + dx * math.sin(r) + dy * math.cos(r))


def draw_stamp(cv, x0, y0, x1, y1, ang, col, country, kind, date, port):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for inset, wd in ((0, 2), (5, 1)):
        corners = [(x0 + inset, y0 + inset), (x1 - inset, y0 + inset),
                   (x1 - inset, y1 - inset), (x0 + inset, y1 - inset)]
        rc = [_rot(px, py, cx, cy, ang) for px, py in corners]
        cv.polyline(rc + [rc[0]], col, wd)
    # deterministic ink speckle along the border
    for i in range(26):
        t = (i * 37) % 100 / 100.0
        px = x0 + 4 + t * (x1 - x0 - 8)
        py = y0 + 3 + ((i * 53) % 7)
        qx, qy = _rot(px, py, cx, cy, ang)
        cv.disc(qx, qy, 1, col)
    hh = y1 - y0
    draw_centered(cv, "sans_bold", 14, cx, y0 + int(hh * 0.11), country, col)
    draw_centered(cv, "sans_bold", 11, cx, y0 + int(hh * 0.36), kind, col)
    draw_centered(cv, "sans_bold", 13, cx, y0 + int(hh * 0.57), date, col)
    draw_centered(cv, "sans", 9, cx, y0 + int(hh * 0.80), port, col)


def _circle(cv, cx, cy, r, col, width=2):
    pts = []
    for a in range(0, 361, 6):
        rad = math.radians(a)
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
    cv.polyline(pts, col, width)


def draw_round_stamp(cv, cx, cy, r, col, lines, top=18):
    """Round fee stamp: double ring with centred lines of text."""
    _circle(cv, cx, cy, r, col, 2)
    _circle(cv, cx, cy, r - 6, col, 1)
    y = cy - top
    for size, text in lines:
        draw_centered(cv, "sans_bold", size, cx, y, text, col)
        y += size + 5


def _arc(cv, cx, cy, r, a0, a1, col, width=1):
    """Draw part of a circle outline, angles in degrees."""
    pts = []
    a = a0
    while a <= a1:
        rad = math.radians(a)
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
        a += 6
    cv.polyline(pts, col, width)


def draw_waves(cv, x0, x1):
    """Dense sine guilloche across a page (Altvarra-style)."""
    for yb in range(30, 611, 14):
        cv.sine(x0 + 16, x0 + 472, yb, 5, 80, GUILL, 1)


def draw_rosette(cv, cx, cy):
    """Concentric guilloche circles + one dashed ring."""
    for r in (55, 66, 77, 88, 99, 110):
        _circle(cv, cx, cy, r, GUILL, 1)
    for a0 in range(0, 360, 24):
        _arc(cv, cx, cy, 44, a0, a0 + 12, GUILL, 1)


def draw_barcode(cv, x, y, w, h, text):
    """Deterministic barcode strip: 3 bars per character, tiled to w."""
    units = []
    for ch in text:
        v = ord(ch)
        for k in range(3):
            bw = 1 + ((v >> (k * 2)) & 3) % 3
            gap = 1 + ((v >> (k * 2 + 1)) & 1)
            units.append((bw, gap))
    bx = x
    while bx < x + w:
        for bw, gap in units:
            if bx >= x + w:
                break
            cv.rect(bx, y, min(bx + bw - 1, x + w - 1), y + h, fill=INK)
            bx += bw + gap


def _catmull(pts, samples=10):
    """Catmull-Rom spline through pts -> smooth flowing polyline."""
    out = []
    p = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(len(p) - 3):
        p0, p1, p2, p3 = p[i], p[i + 1], p[i + 2], p[i + 3]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(p[-2])
    return out


def draw_signature_cursive(cv, x0, y0):
    """Hand-drawn cursive 'S. A. Hadri' (smooth splines, not a zigzag)."""
    s_cap = [(0, 3), (1, -3), (3, -10), (6, -14), (9, -13), (10, -8),
             (8, -4), (5, -2), (4, 1), (6, 4), (9, 4), (11, 1), (12, -1)]
    a_cap = [(18, 2), (19, -6), (21, -13), (23, -14), (24, -8),
             (25, -1), (26, 2), (21, -6), (26, -6)]
    hadri = [(34, 2), (35, -7), (36, -14), (37, -7), (38, 0), (39, -7),
             (41, -13), (43, -12), (44, -5), (45, 1), (48, 0), (49, -6),
             (51, -7), (53, -5), (53, 0), (52, 2), (50, 2), (56, 0),
             (57, -7), (59, -13), (61, -13), (62, -7), (62, 0), (62, 5),
             (65, 0), (66, -6), (68, -7), (70, -5), (70, 0), (73, -1),
             (74, -7), (75, -7), (74, 0), (73, 2)]
    flourish = [(2, 9), (30, 12), (70, 11), (105, 7), (120, 3)]
    for stroke in (s_cap, a_cap, hadri, flourish):
        pts = [(x0 + dx, y0 + dy) for dx, dy in stroke]
        cv.polyline(_catmull(pts), INK, 2)
    cv.disc(x0 + 14, y0 + 2, 1, INK)
    cv.disc(x0 + 28, y0 + 2, 1, INK)
    cv.disc(x0 + 74, y0 - 11, 1, INK)


def draw_sheared_text(cv, font_name, size, x, y, text, col, shear=0.35):
    """Italic-looking text by shearing each glyph (fallback signature)."""
    base = round(size * 0.8)
    px = float(x)
    for ch in text:
        code = ord(ch)
        if code not in _FONTS[font_name]:
            px += size * 0.25
            continue
        adv, ox, oy, _sw, _sh, pts = _scaled_glyph(font_name, size, code)
        for dx, dy, cov in pts:
            xx = int(px) + ox + dx + int(shear * (base - (oy + dy)))
            yy = int(y) + oy + dy
            if 0 <= xx < cv.w and 0 <= yy < cv.h:
                i = (yy * cv.w + xx) * 3
                if cov == 255:
                    cv.pix[i], cv.pix[i + 1], cv.pix[i + 2] = col
                else:
                    cv.pix[i] = (col[0] * cov + cv.pix[i] * (255 - cov)) // 255
                    cv.pix[i + 1] = (col[1] * cov + cv.pix[i + 1] * (255 - cov)) // 255
                    cv.pix[i + 2] = (col[2] * cov + cv.pix[i + 2] * (255 - cov)) // 255
        px += adv
    return px


# ---------------------------------------------------------------- layout
def field(cv, x, y, label, value, vsize=15):
    draw_text(cv, "sans", 9, x, y, label, GREY)
    draw_text(cv, "serif_bold", vsize, x, y + 11, value, INK)


def vfield(cv, x, y, label, value):
    """Small label/value pair for the visa box (label 8px, value 11px)."""
    draw_text(cv, "sans", 8, x, y, label, GREY)
    draw_text(cv, "serif_bold", 11, x, y + 9, value, INK)


def build():
    here = os.path.dirname(os.path.abspath(__file__))
    init_fonts(os.path.join(here, "fonts.bin"))
    portrait = load_rgb(os.path.join(here, "portrait.rgb"), 142, 182)
    ghost = load_rgb(os.path.join(here, "ghost.rgb"), 70, 90)
    cv = Canvas(W, H, DESK)
    # spread pages
    cv.rect(14, 14, 502, 626, fill=PAPER)
    cv.rect(522, 14, 1010, 626, fill=PAPER)
    cv.rect(502, 14, 522, 626, fill=(24, 28, 38))
    cv.line(511, 14, 511, 626, (52, 60, 76), 1)
    for px0 in (14, 522):
        cv.rect(px0 + 5, 19, px0 + 483, 621, outline=NAVY, width=2)
        cv.rect(px0 + 10, 24, px0 + 478, 616, outline=GOLD, width=1)
    # dense guilloche waves on both pages (Altvarra-style)
    draw_waves(cv, 14, 502)
    draw_waves(cv, 522, 1010)
    # deterministic paper grain (drawn first, so it stays under the ink)
    _rnd = 12345

    def _next():
        nonlocal _rnd
        _rnd = (_rnd * 1103515245 + 12345) & 0x7FFFFFFF
        return _rnd

    for _ in range(2600):
        nx = 20 + _next() % 980
        ny = 20 + _next() % 600
        if 502 <= nx <= 522:
            continue
        cv._set(nx, ny, (232, 225, 200) if _next() % 2 else (250, 244, 228))
    # (right-page watermark anchor removed in v3: stamp grid is dense)

    # ---------------------------------------------------------- left page
    # rosette + watermark number (drawn first, under the ink)
    draw_rosette(cv, 258, 440)
    draw_centered(cv, "sans", 30, 258, 465, "TS482913", (232, 225, 200))
    # centred emblem + masthead (Kestrava manner: teal serif, red line)
    draw_sun_emblem(cv, 258, 48, 20, TEAL)
    draw_centered(cv, "serif_bold", 22, 258, 70, "REPUBLIC OF TESHMAR",
                  TEAL)
    draw_centered(cv, "serif", 11, 258, 94, "TESHMARA JUMHURIYAT", RED)
    draw_tracked(cv, "sans", 11, 157, 108, "SAFAR • PASSPORT",
                 GOLD_DARK, 13.5)
    cv.line(38, 122, 478, 122, GOLD, 2)
    # photo (photorealistic studio portrait, composited from portrait.rgb)
    cv.rect(38, 134, 188, 316, fill=WHITE)
    blit_rgb(cv, portrait, 142, 182, 42, 138)
    cv.rect(38, 134, 188, 316, outline=NAVY, width=2)
    # cursive signature under the photo
    draw_signature_cursive(cv, 40, 336)
    draw_text(cv, "sans", 8, 40, 354, "TAWQI / SIGNATURE OF HOLDER", GREY)
    # data fields (bilingual labels, invented / English)
    fx = 206
    field(cv, fx, 134, "NAW / TYPE", "P", 14)
    field(cv, fx + 56, 134, "KUD / CODE", "TSM", 14)
    field(cv, fx + 126, 134, "SAFAR NR. / PASSPORT NO.", "TS482913", 14)
    field(cv, fx, 164, "NASAB / SURNAME", "HADRI")
    field(cv, fx, 194, "ISM / GIVEN NAMES", "SELMA AMARA")
    field(cv, fx, 224, "JINSIYA / NATIONALITY", "TESHMARI")
    field(cv, fx, 254, "MILAD / DATE OF BIRTH", "17 AUG 1978")
    field(cv, fx + 196, 254, "JINS / SEX", "F")
    field(cv, fx, 284, "MAWLID / PLACE OF BIRTH", "QARASU")
    draw_text(cv, "sans", 8, 372, 284, "RAQAM / PERSONAL NO.", GREY)
    draw_text(cv, "serif_bold", 13, 372, 295, "780817-4412", INK)
    field(cv, fx, 314, "SUDUR / DATE OF ISSUE", "05 FEB 2024")
    field(cv, fx + 150, 314, "INTIHA / DATE OF EXPIRY", "04 FEB 2034")
    field(cv, fx, 344, "SULTA / AUTHORITY", "PASSPORT OFFICE, QARASU")
    field(cv, fx, 374, "MIHNA / OCCUPATION", "CARAVAN MASTER")
    # observations + ghost portrait
    draw_text(cv, "sans_bold", 10, 38, 404, "MULAHAZA / OBSERVATIONS", NAVY)
    text_block(cv, "serif", 12, 38, 418,
               "Registered resident of the Teshmar Salt Road (SR-2). Land "
               "departure by the Salt Road only; see endorsement on page 3.",
               INK, 360, 14)
    blit_rgb(cv, ghost, 70, 90, 408, 398)
    # MRZ
    mrz1, mrz2 = build_mrz()
    cv.rect(38, 520, 478, 596, fill=PAPER_DIM, outline=NAVY, width=1)
    draw_tracked(cv, "sans", 15, 52, 532, mrz1, INK, 9.4)
    draw_tracked(cv, "sans", 15, 52, 560, mrz2, INK, 9.4)
    draw_text(cv, "sans", 10, 38, 606, "02", GREY)

    # --------------------------------------------------------- right page
    draw_text(cv, "serif_bold", 22, 546, 36, "DUKHUL • VIZA • VISAS",
              TEAL)
    draw_tracked(cv, "sans", 10, 546, 64, "SALT ROAD - DESERT CROSSINGS",
                 GOLD_DARK, 12.0)
    draw_text(cv, "sans", 10, 962, 36, "03", GREY)
    cv.line(546, 88, 986, 88, GOLD, 2)
    # endorsement box: dated, place-specific caravan rules
    cv.rect(546, 96, 986, 192, fill=PAPER, outline=NAVY, width=2)
    draw_text(cv, "sans_bold", 11, 562, 104,
              "ENDORSEMENT 1 / 2024 - SALT ROAD", NAVY)
    text_block(cv, "serif", 10, 562, 124,
               "This passport is valid for Salt Road travel only. Caravan "
               "crossings are permitted only in daylight, 1 MAR - 30 NOV. "
               "The Salt Road is closed in sandstorm season, 1 DEC - 28 "
               "FEB. Valid with licence C-4417.",
               INK, 340, 14)
    # round caravan-toll stamp overlapping the endorsement box corner
    draw_round_stamp(cv, 945, 108, 40, (150, 60, 40),
                     [(6, "CARAVAN TOLL"), (10, "9 TKD"),
                      (6, "PAID - QARASU"), (5, "04 MAR 2024")])
    # neighbour visitor visa sticker box
    cv.rect(546, 200, 986, 288, fill=(232, 238, 222), outline=NAVY, width=2)
    draw_text(cv, "sans_bold", 11, 562, 206, "DARQESH - VISITOR VISA", NAVY)
    draw_text(cv, "sans_bold", 10, 850, 207, "No. DQ 3105 2214",
              (150, 60, 40))
    vfield(cv, 562, 218, "TYPE", "C - SINGLE ENTRY")
    vfield(cv, 562, 238, "VALID FROM", "12 AUG 2024")
    vfield(cv, 562, 258, "ISSUED AT", "QARASU, 28 JUL 2024")
    vfield(cv, 768, 218, "DURATION OF STAY", "15 DAYS")
    vfield(cv, 768, 238, "UNTIL", "11 SEP 2024")
    vfield(cv, 768, 258, "FEE", "30 DQD")
    draw_barcode(cv, 562, 279, 338, 8, "DQ31052214")
    # 8 stamps, 2-column grid, alternating shapes and ink colours
    draw_stamp(cv, 546, 300, 746, 372, -3, (36, 84, 160), "TESHMAR",
               "DEPARTED", "12 AUG 2024", "SALT ROAD GATE 1")
    draw_stamp(cv, 768, 300, 968, 372, 4, (24, 110, 170), "DARQESH",
               "ARRIVAL", "15 AUG 2024", "MERID GATE")
    draw_stamp(cv, 546, 380, 746, 452, 3, (110, 60, 140), "DARQESH",
               "DEPARTURE", "28 AUG 2024", "MERID GATE")
    draw_round_stamp(cv, 868, 416, 36, (34, 110, 70),
                     [(7, "KARUN"), (8, "ADMITTED"), (6, "02 SEP 2024"),
                      (5, "DESERT POST")], top=20)
    draw_stamp(cv, 546, 460, 746, 532, -4, (150, 60, 40), "KARUN",
               "DEPARTURE", "16 SEP 2024", "DESERT POST")
    draw_stamp(cv, 768, 460, 968, 532, 5, (30, 90, 120), "SARUN",
               "ENTRY", "11 MAR 2025", "CARAVAN PERMIT")
    draw_round_stamp(cv, 646, 576, 34, (24, 110, 170),
                     [(6, "TESHMAR"), (9, "ENTRY"), (6, "20 SEP 2024"),
                      (5, "SALT ROAD")], top=20)
    draw_stamp(cv, 768, 540, 968, 612, -3, (24, 48, 84), "SARUN",
               "EXIT", "29 MAR 2025", "SALT ROAD")
    draw_text(cv, "sans", 10, 940, 606, "TS482913", GREY)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    write_png(cv, os.path.join(out_dir, "entry.png"))


if __name__ == "__main__":
    main()
