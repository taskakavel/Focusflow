#!/usr/bin/env python3
"""Generate FocusFlow 'Tomato Demon' icons (180/192/512) using only stdlib.

Design: dark navy background, indigo timer-ring arc, angry red tomato
with devil horns, stem, fangs, tongue and slanted brows. Fully opaque.
"""
import math
import struct
import zlib


def chunk(tag, data):
    c = tag + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))


def write_png(path, size, pixels):
    raw = b""
    for row in pixels:
        raw += b"\x00"
        for r, g, b in row:
            raw += bytes((r, g, b, 255))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def clampf(v):
    return max(0.0, min(1.0, v))


def clamp(v):
    return max(0, min(255, int(round(v))))


def mix(c1, c2, t):
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(3))


def blend(cur, col, cov):
    if cov <= 0:
        return cur
    a = clampf(cov)
    return tuple(cur[i] * (1 - a) + col[i] * a for i in range(3))


def make_icon(S):
    # Coverage helpers (1 inside, 0 outside, ~1px AA band)
    def band(edge, d):
        return clampf(edge - d + 0.5)

    def circle_cov(px, py, cx, cy, r):
        return band(r, math.hypot(px - cx, py - cy))

    def ellipse_cov(px, py, cx, cy, rx, ry):
        e = math.sqrt(((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2)
        return clampf(1 - e + 0.5)

    def seg_dist(px, py, a, b):
        ax, ay = a
        bx, by = b
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        t = (wx * vx + wy * vy) / (vx * vx + vy * vy)
        t = max(0.0, min(1.0, t))
        return math.hypot(wx - t * vx, wy - t * vy)

    def capsule_cov(px, py, a, b, w):
        return band(w, seg_dist(px, py, a, b))

    def tri_in(px, py, p1, p2, p3):
        s1 = (px - p1[0]) * (p2[1] - p1[1]) - (py - p1[1]) * (p2[0] - p1[0])
        s2 = (px - p2[0]) * (p3[1] - p2[1]) - (py - p2[1]) * (p3[0] - p2[0])
        s3 = (px - p3[0]) * (p1[1] - p3[1]) - (py - p3[1]) * (p1[0] - p3[0])
        same = (s1 >= 0 and s2 >= 0 and s3 >= 0) or (s1 <= 0 and s2 <= 0 and s3 <= 0)
        return 1.0 if same else 0.0

    def arc_cov(px, py, cx, cy, r_out, r_in, gap_from, gap_to):
        r = math.hypot(px - cx, py - cy)
        ang = math.degrees(math.atan2(py - cy, px - cx))
        if gap_from <= ang <= gap_to:
            return 0.0
        return min(band(r_out, r), band(r, r_in))

    # Palette
    bg_top = (49, 46, 129)      # indigo-900
    bg_bot = (15, 23, 42)       # slate-900
    ring_a = (165, 180, 252)    # indigo-300
    ring_b = (99, 102, 241)     # indigo-500
    tom_top = (248, 113, 113)   # red-400
    tom_bot = (153, 27, 27)     # red-800
    gloss_c = (255, 200, 200)
    stem_c = (34, 197, 94)
    stem_d = (22, 101, 52)
    horn_c = (120, 12, 12)
    dark = (17, 24, 39)
    white = (255, 255, 255)
    tongue_c = (239, 68, 68)

    cx = cy = 0.5
    horn_paths = [
        [(0.415, 0.405), (0.33, 0.235), (0.40, 0.13)],   # left
        [(0.585, 0.405), (0.67, 0.235), (0.60, 0.13)],   # right
    ]

    rows = []
    for y in range(S):
        row = []
        for x in range(S):
            acc = [0.0, 0.0, 0.0]
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    px = (x + sx) / S
                    py = (y + sy) / S

                    c = mix(bg_top, bg_bot, py)

                    # Indigo timer-ring arc (gap at the bottom)
                    cov = arc_cov(px, py, cx, cy, 0.44, 0.365, -105, -75)
                    c = blend(c, mix(ring_a, ring_b, py), cov * 0.95)

                    # Tomato body
                    cov = circle_cov(px, py, 0.5, 0.55, 0.30)
                    c = blend(c, mix(tom_top, tom_bot, py), cov)

                    # Gloss highlight
                    cov = ellipse_cov(px, py, 0.395, 0.465, 0.06, 0.045)
                    c = blend(c, gloss_c, cov * 0.4)

                    # Stem + leaves
                    c = blend(c, stem_d, capsule_cov(px, py, (0.5, 0.258), (0.5, 0.19), 0.03))
                    c = blend(c, stem_c, capsule_cov(px, py, (0.5, 0.235), (0.41, 0.205), 0.022))
                    c = blend(c, stem_c, capsule_cov(px, py, (0.5, 0.235), (0.59, 0.205), 0.022))

                    # Devil horns
                    for hp in horn_paths:
                        c = blend(c, horn_c, capsule_cov(px, py, hp[0], hp[1], 0.062))
                        c = blend(c, horn_c, capsule_cov(px, py, hp[1], hp[2], 0.05))

                    # Mouth, tongue, fangs
                    cov = ellipse_cov(px, py, 0.5, 0.655, 0.095, 0.045)
                    c = blend(c, dark, cov)
                    c = blend(c, tongue_c, ellipse_cov(px, py, 0.5, 0.668, 0.034, 0.016))
                    t1 = tri_in(px, py, (0.448, 0.632), (0.478, 0.632), (0.463, 0.668))
                    t2 = tri_in(px, py, (0.552, 0.632), (0.522, 0.632), (0.537, 0.668))
                    c = blend(c, white, max(t1, t2))

                    # Eyes (white + angry pupils toward center) + glints
                    c = blend(c, white, ellipse_cov(px, py, 0.408, 0.555, 0.047, 0.055))
                    c = blend(c, white, ellipse_cov(px, py, 0.592, 0.555, 0.047, 0.055))
                    c = blend(c, dark, ellipse_cov(px, py, 0.424, 0.565, 0.019, 0.031))
                    c = blend(c, dark, ellipse_cov(px, py, 0.576, 0.565, 0.019, 0.031))
                    c = blend(c, white, circle_cov(px, py, 0.428, 0.556, 0.008))
                    c = blend(c, white, circle_cov(px, py, 0.572, 0.556, 0.008))

                    # Angry slanted eyebrows
                    c = blend(c, dark, capsule_cov(px, py, (0.36, 0.505), (0.448, 0.532), 0.026))
                    c = blend(c, dark, capsule_cov(px, py, (0.64, 0.505), (0.552, 0.532), 0.026))

                    acc[0] += c[0]
                    acc[1] += c[1]
                    acc[2] += c[2]
            row.append((clamp(acc[0] / 4), clamp(acc[1] / 4), clamp(acc[2] / 4)))
        rows.append(row)
    return rows


if __name__ == "__main__":
    for s, name in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        write_png(name, s, make_icon(s))
        print(f"{name} ({s}x{s}) generated")