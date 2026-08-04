# -*- coding: utf-8 -*-
"""生成"今天吃什么"App 图标（纯标准库，无需安装任何包）。"""
import zlib, struct, os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "icons")


def chunk(tag, data):
    payload = tag + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def write_png(path, w, h, pixels):
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter 类型 0（无过滤）
        for x in range(w):
            r, g, b, a = pixels[y][x]
            raw += bytes((r, g, b, a))
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def blend_over(bg, fg, alpha):
    return tuple(int(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def in_rounded_rect(x, y, S, rad):
    cx = min(max(x, rad), S - 1 - rad)
    cy = min(max(y, rad), S - 1 - rad)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= rad * rad


def dist_to_segment(x, y, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def make_icon(S, path):
    top, bottom = (255, 154, 86), (255, 106, 61)
    white, steam = (255, 255, 255), (255, 255, 255)
    rad = S * 0.22
    bowl = (S * 0.50, S * 0.58, S * 0.235)
    ing = [
        (S * 0.42, S * 0.55, S * 0.045, (211, 84, 0)),
        (S * 0.55, S * 0.50, S * 0.040, (247, 183, 51)),
        (S * 0.50, S * 0.63, S * 0.038, (76, 175, 80)),
        (S * 0.62, S * 0.60, S * 0.035, (192, 57, 43)),
    ]
    caps = [  # (起点x, 起点y, 终点x, 终点y, 半径)
        (S * 0.38, S * 0.29, S * 0.38, S * 0.17, S * 0.036),
        (S * 0.50, S * 0.27, S * 0.50, S * 0.12, S * 0.042),
        (S * 0.62, S * 0.29, S * 0.62, S * 0.17, S * 0.036),
    ]
    pixels = []
    for y in range(S):
        row = []
        bg = lerp(top, bottom, y / (S - 1))
        for x in range(S):
            if not in_rounded_rect(x, y, S, rad):
                row.append((0, 0, 0, 0))
                continue
            col = bg
            bx, by, br = bowl
            if (x - bx) ** 2 + (y - by) ** 2 <= br * br:
                col = white
                for ix, iy, ir, ic in ing:
                    if (x - ix) ** 2 + (y - iy) ** 2 <= ir * ir:
                        col = ic
                        break
            for x1, y1, x2, y2, r in caps:
                if dist_to_segment(x, y, x1, y1, x2, y2) <= r:
                    col = blend_over(col, steam, 0.82)
                    break
            row.append((col[0], col[1], col[2], 255))
        pixels.append(row)
    write_png(path, S, S, pixels)


os.makedirs(OUT_DIR, exist_ok=True)
make_icon(512, os.path.join(OUT_DIR, "icon-512.png"))
make_icon(192, os.path.join(OUT_DIR, "icon-192.png"))
make_icon(180, os.path.join(OUT_DIR, "apple-touch-icon-180.png"))
print("图标已生成:", OUT_DIR)
