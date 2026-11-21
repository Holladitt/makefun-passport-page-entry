"""Prep script (local only, NOT part of the entry): convert the generated
passport photo into raw RGB assets that main.py can blit with stdlib only.
- portrait.rgb: 142x182, the photo pasted into the data page
- ghost.rgb:   70x90, the same photo pre-blended toward paper colour at
  16% alpha, used as the faint ghost portrait watermark
"""
from PIL import Image

SRC = "media-generation-teshmar-portrait-0-6617f06f-024c-4c35-8445-d8a13988572f.webp"
PAPER = (247, 240, 222)

im = Image.open(SRC).convert("RGB")
print("source:", im.size)
# head-and-shoulders crop: hair top through upper chest
crop = im.crop((232, 64, 1368, 1520))
print("crop:", crop.size, "aspect:", crop.size[0] / crop.size[1])

photo = crop.resize((142, 182), Image.LANCZOS)
with open("portrait.rgb", "wb") as f:
    f.write(photo.tobytes())
print("portrait.rgb:", 142 * 182 * 3, "bytes")

ghost = crop.resize((70, 90), Image.LANCZOS)
px = ghost.load()
for y in range(90):
    for x in range(70):
        r, g, b = px[x, y]
        px[x, y] = tuple(int(PAPER[c] * 0.84 + (r, g, b)[c] * 0.16)
                         for c in range(3))
with open("ghost.rgb", "wb") as f:
    f.write(ghost.tobytes())
print("ghost.rgb:", 70 * 90 * 3, "bytes")
