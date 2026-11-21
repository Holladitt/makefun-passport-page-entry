"""The Passport Page of a Country That Isn't There — make.fun entry.

Draws one invented passport spread (1024x640) to /output/entry.png.
Stdlib only (Python 3.13, no network, no external assets): a small
software rasterizer, a DejaVu glyph atlas read from fonts.bin beside
this file, and a hand-rolled PNG writer. Deterministic: same bytes
every run.

Concept: the Republic of Kalnara, an archipelago that runs on ferries.
Holder Mara Elena Ilves, ferry captain of Port Anselm. Her passport
carries a proper ICAO MRZ, four neighbour stamps that form a
plausible ferry-hopping history after the issue date, and one telling
condition: valid for ferry routes only, not for air travel.
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
    doc = "KAL041883"
    nat = "KAL"
    dob = "880314"
    exp = "340102"
    sex = "F"
    personal = "<" * 14
    c1 = _check_digit(doc)
    c2 = _check_digit(dob)
    c3 = _check_digit(exp)
    c4 = _check_digit(personal)
    comp = _check_digit(doc + c1 + dob + c2 + exp + c3 + personal + c4)
    line1 = "P<KALILVES<<MARA<ELENA"
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


def draw_shield(cv, cx, cy, s, col):
    """Small shield outline with an anchor inside (cover emblem)."""
    w2, h2 = s * 0.42, s * 0.52
    pts = [(cx - w2, cy - h2), (cx + w2, cy - h2), (cx + w2, cy + h2 * 0.25),
           (cx, cy + h2), (cx - w2, cy + h2 * 0.25)]
    cv.polygon(pts, outline=col)
    draw_anchor(cv, cx, cy - s * 0.02, s * 0.62, col, 2)


# -------------------------------------------------------------- portrait
def draw_portrait(cv, x0, y0, x1, y1):
    """Document photo: ferry captain Mara Ilves, flat dignified style."""
    cx = (x0 + x1) // 2
    cv.gradient(x0, y0, x1 - x0, y1 - y0, SEA_TOP, SEA_BOT)
    for wy, ww in ((y1 - 38, 2), (y1 - 26, 2), (y1 - 14, 2)):
        pts = []
        x = x0
        while x <= x1:
            pts.append((x, wy + 3 * math.sin(2 * math.pi * x / 70)))
            x += 4
        cv.polyline(pts, (86, 140, 180), ww)
    # shoulders / uniform
    cv.polygon([(x0 + 8, y1), (x0 + 20, y1 - 52), (cx - 20, y1 - 64),
                (cx + 20, y1 - 64), (x1 - 20, y1 - 52), (x1 - 8, y1)],
               fill=JACKET)
    # shirt + tie
    cv.polygon([(cx - 13, y1 - 60), (cx + 13, y1 - 60), (cx, y1 - 28)],
               fill=(245, 245, 240))
    cv.polygon([(cx - 4, y1 - 60), (cx + 4, y1 - 60), (cx + 3, y1 - 32),
                (cx, y1 - 26), (cx - 3, y1 - 32)], fill=(24, 26, 34))
    # epaulettes
    cv.rect(x0 + 14, y1 - 56, x0 + 38, y1 - 48, fill=GOLD)
    cv.rect(x1 - 38, y1 - 56, x1 - 14, y1 - 48, fill=GOLD)
    # neck, ears, bun, head
    cv.rect(cx - 10, y0 + 100, cx + 10, y0 + 128, fill=SKIN_D)
    cv.ellipse(x0 + 34, y0 + 62, x0 + 42, y0 + 76, fill=SKIN)
    cv.ellipse(x1 - 42, y0 + 62, x1 - 34, y0 + 76, fill=SKIN)
    cv.disc(cx, y0 + 8, 11, HAIR)
    cv.ellipse(cx - 38, y0 + 10, cx + 38, y0 + 62, fill=HAIR)
    cv.ellipse(cx - 34, y0 + 20, cx + 34, y0 + 98, fill=SKIN)
    # hair fringe over the forehead
    pts = [(cx - 34, y0 + 52)]
    for a in range(180, 361, 12):
        r = math.radians(a)
        pts.append((cx + 34 * math.cos(r), y0 + 44 + 18 * math.sin(r)))
    pts.append((cx + 34, y0 + 52))
    cv.polygon(pts, fill=HAIR)
    # captain's cap
    cv.polygon([(cx - 37, y0 + 32), (cx - 31, y0 + 12), (cx + 31, y0 + 12),
                (cx + 37, y0 + 32)], fill=(18, 34, 66))
    cv.ellipse(cx - 40, y0 + 26, cx + 40, y0 + 36, fill=(14, 26, 50))
    draw_anchor(cv, cx, y0 + 21, 13, GOLD, 1)
    # face
    cv.line(cx - 21, y0 + 54, cx - 9, y0 + 52, HAIR, 2)
    cv.line(cx + 9, y0 + 52, cx + 21, y0 + 54, HAIR, 2)
    cv.ellipse(cx - 19, y0 + 60, cx - 11, y0 + 64, fill=(30, 24, 20))
    cv.ellipse(cx + 11, y0 + 60, cx + 19, y0 + 64, fill=(30, 24, 20))
    cv.line(cx, y0 + 64, cx - 1, y0 + 76, SKIN_D, 2)
    cv.line(cx - 5, y0 + 77, cx + 4, y0 + 77, SKIN_D, 1)
    cv.ellipse(cx - 7, y0 + 84, cx + 7, y0 + 88, fill=ROSE)


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
    draw_centered(cv, "sans_bold", 14, cx, y0 + 10, country, col)
    draw_centered(cv, "sans_bold", 11, cx, y0 + 32, kind, col)
    draw_centered(cv, "sans_bold", 13, cx, y0 + 50, date, col)
    draw_centered(cv, "sans", 9, cx, y0 + 71, port, col)


# ---------------------------------------------------------------- layout
def field(cv, x, y, label, value, vsize=15):
    draw_text(cv, "sans", 9, x, y, label, GREY)
    draw_text(cv, "serif_bold", vsize, x, y + 11, value, INK)


def build():
    init_fonts(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fonts.bin"))
    cv = Canvas(W, H, DESK)
    # spread pages
    cv.rect(14, 14, 502, 626, fill=PAPER)
    cv.rect(522, 14, 1010, 626, fill=PAPER)
    cv.rect(502, 14, 522, 626, fill=(24, 28, 38))
    cv.line(511, 14, 511, 626, (52, 60, 76), 1)
    for px0 in (14, 522):
        cv.rect(px0 + 5, 19, px0 + 483, 621, outline=NAVY, width=2)
        cv.rect(px0 + 10, 24, px0 + 478, 616, outline=GOLD, width=1)
    # faint guilloche on both pages
    for px0 in (14, 522):
        for yb in (150, 330, 500):
            cv.sine(px0 + 16, px0 + 472, yb, 6, 90, GUILL, 1)
    # faint watermark anchor on the right page
    draw_anchor(cv, 766, 545, 110, (228, 221, 198), 5)

    # ---------------------------------------------------------- left page
    draw_shield(cv, 56, 56, 34, NAVY)
    draw_text(cv, "serif_bold", 24, 86, 36, "REPUBLIC OF KALNARA", INK)
    draw_tracked(cv, "sans", 11, 88, 66, "PASSPORT / PASPORT",
                 GOLD_DARK, 13.5)
    cv.line(38, 88, 478, 88, GOLD, 2)
    # photo
    cv.rect(38, 102, 188, 292, fill=WHITE)
    draw_portrait(cv, 42, 106, 184, 288)
    cv.rect(38, 102, 188, 292, outline=NAVY, width=2)
    # data fields
    fx = 206
    field(cv, fx, 102, "TYPE", "P", 14)
    field(cv, fx + 56, 102, "CODE", "KAL", 14)
    field(cv, fx + 126, 102, "No.", "KAL041883", 14)
    field(cv, fx, 132, "SURNAME", "ILVES")
    field(cv, fx, 162, "GIVEN NAMES", "MARA ELENA")
    field(cv, fx, 192, "NATIONALITY", "KALNARAN")
    field(cv, fx, 222, "DATE OF BIRTH", "14 MAR 1988")
    field(cv, fx + 196, 222, "SEX", "F")
    field(cv, fx, 252, "PLACE OF BIRTH", "PORT ANSELM, KALNARA")
    field(cv, fx, 282, "DATE OF ISSUE", "02 JAN 2024")
    field(cv, fx + 150, 282, "DATE OF EXPIRY", "02 JAN 2034")
    field(cv, fx, 312, "AUTHORITY", "PORT ANSELM")
    field(cv, fx, 342, "OCCUPATION", "FERRY CAPTAIN")
    cv.line(38, 388, 478, 388, LGREY, 1)
    # signature + seal
    cv.polyline([(64, 426), (72, 416), (80, 424), (88, 418), (96, 426),
                 (104, 420), (112, 428), (120, 416), (128, 426), (136, 418),
                 (144, 426), (152, 420), (162, 428), (172, 418), (180, 426)],
                INK, 2)
    draw_text(cv, "sans", 8, 64, 446, "SIGNATURE OF HOLDER", GREY)
    cv.ring(400, 425, 30, 24, NAVY)
    draw_anchor(cv, 400, 418, 26, NAVY, 2)
    draw_centered(cv, "sans_bold", 8, 400, 438, "KALNARA", NAVY)
    # MRZ
    mrz1, mrz2 = build_mrz()
    cv.rect(38, 520, 478, 596, fill=PAPER_DIM, outline=NAVY, width=1)
    draw_tracked(cv, "sans", 15, 52, 532, mrz1, INK, 9.4)
    draw_tracked(cv, "sans", 15, 52, 560, mrz2, INK, 9.4)
    draw_text(cv, "sans", 10, 38, 606, "04", GREY)

    # --------------------------------------------------------- right page
    draw_text(cv, "serif_bold", 22, 546, 36, "VISAS", INK)
    draw_tracked(cv, "sans", 10, 546, 64, "FERRY ROUTES - COASTAL DISTRICTS",
                 GOLD_DARK, 12.0)
    cv.line(546, 88, 986, 88, GOLD, 2)
    stamps = [
        (546, 106, -4, (36, 84, 160), "SELVANE", "ARRIVAL", "18 MAR 2024",
         "PORT OF VELKIR"),
        (768, 106, 3, (110, 60, 140), "DRAKMOOR", "DEPARTURE", "02 APR 2024",
         "HARBOUR GATE"),
        (546, 214, 5, (34, 110, 70), "ILYNDOR", "ARRIVAL", "21 JUN 2024",
         "FERRY TERMINAL"),
        (768, 214, -3, (150, 60, 40), "TARNOVIA", "DEPARTURE", "09 SEP 2024",
         "NORTH PIER"),
    ]
    for x0, y0, ang, col, ctry, kind, date, port in stamps:
        draw_stamp(cv, x0, y0, x0 + 200, y0 + 92, ang, col, ctry, kind,
                   date, port)
    # conditions box + fee stamp
    cv.rect(546, 330, 986, 448, fill=PAPER, outline=NAVY, width=2)
    draw_text(cv, "sans_bold", 12, 562, 344, "CONDITIONS OF ISSUE", NAVY)
    text_block(cv, "serif", 13, 562, 368,
               "This passport is valid for ferry routes only. Not valid "
               "for air travel. The holder is a licensed master of the "
               "Kalnara Coastal Ferry Service.",
               INK, 408, 20)
    fx0, fy0, fx1, fy1 = 800, 306, 968, 340
    fcx, fcy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
    corners = [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)]
    rc = [_rot(px, py, fcx, fcy, -5) for px, py in corners]
    cv.polygon(rc, fill=(247, 240, 222), outline=GOLD_DARK)
    draw_centered(cv, "sans_bold", 11, fcx, fcy - 7,
                  "PASSAGE FEE PAID - 12 KRD", GOLD_DARK)
    # observations
    draw_text(cv, "sans_bold", 10, 546, 466, "OBSERVATIONS", NAVY)
    draw_text(cv, "serif", 12, 546, 482,
              "Holder is exempt from coastal tolls on routes 1-9.", INK)
    draw_text(cv, "sans", 10, 962, 606, "05", GREY)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    write_png(cv, os.path.join(out_dir, "entry.png"))


if __name__ == "__main__":
    main()
