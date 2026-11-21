"""Prep script (local only, NOT part of the entry): convert the generated
passport photo into raw RGB assets that main.py can blit with stdlib only.
- portrait.rgb: 142x182, the photo pasted into the data page
- ghost.rgb:   70x90, the same photo pre-blended toward paper colour at
  16% alpha, used as the faint ghost portrait watermark
"""
from PIL import Image

SRC = "media-generation-portrait-photo-0-85e0f99f-de53-4649-a2c0-db6704cb496d.png"
PAPER = (247, 240, 222)

im = Image.open(SRC).convert("RGB")
print("source:", im.size)
# head-and-shoulders crop: cap through upper chest
crop = im.crop((0, 100, 1120, 1540))
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
