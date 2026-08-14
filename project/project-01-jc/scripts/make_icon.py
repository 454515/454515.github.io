"""Generate assets/icon.ico (multi-size) for the 检测识别 app.

Pure Pillow drawing (no font dependency): a blue rounded tile with a white
ID card, two grey text-placeholder lines and a red corner stamp.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
BASE = 1024


def _rounded(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


img = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Blue rounded background
_rounded(d, (32, 32, 992, 992), 200, (30, 108, 224, 255))
# White ID card
_rounded(d, (220, 280, 804, 744), 60, (255, 255, 255, 255))
# Two grey text-placeholder lines
for y in (400, 500):
    _rounded(d, (300, y, 640, y + 44), 22, (214, 220, 230, 255))
# Short third line (id number)
_rounded(d, (300, 600, 500, 644), 22, (214, 220, 230, 255))
# Red corner stamp (top-right of card)
_rounded(d, (640, 340, 740, 440), 40, (222, 66, 66, 255))

sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(OUT, format="ICO", sizes=sizes)
print(f"wrote {OUT} ({[s[0] for s in sizes]})")
