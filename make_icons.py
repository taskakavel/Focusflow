#!/usr/bin/env python3
"""Generate FocusFlow 'Playful Angry Tomato' icons (180/192/512) using only stdlib.

Design: dark navy background, indigo timer-ring arc, a big round RED tomato
with a small green leaf-stem, two small black horns, big white eyes with
angry pupils, a little frown with fangs and tongue. Playful, high-contrast.
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

    def arc_cov(px, py, cx, cy, r_out, r_in, gap_from, gap_to):
        r = math.hypot(px - cx, py - cy)
        ang = math.degrees(math.atan2(py - cy, px - cx))
        if gap_from <= ang <= gap_to:
            return 0.0
        return min(band(r_out, r), band(r, r_in))

    # Palette
    bg_top = (49, 46, 129)
    bg_bot = (15, 23, 42)
    ring_a = (165, 180, 252)
    ring_b = (99, 102, 241)
    tom_a = (252, 165, 165)     # light red
    tom_b = (220, 38, 38)       # strong red
    gloss = (255, 228, 228)
    stem = (74, 222, 128)
    stem_d = (22, 101, 52)
    horn = (60, 20, 20)
    dark = (20, 15, 15)
    white = (255, 255, 255)
    tongue = (248, 113, 113)

    cx = cy = 0.5

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

                    # Indigo ring arc (gap at bottom)
                    cov = arc_cov(px, py, cx, cy, 0.44, 0.375, -105, -75)
                    c = blend(c, mix(ring_a, ring_b, py), cov * 0.95)

                    # Tomato body (big round, slightly below center)
                    cov = circle_cov(px, py, 0.5, 0.56, 0.30)
                    c = blend(c, mix(tom_a, tom_b, py), cov)

                    # Gloss highlight
                    cov = ellipse_cov(px, py, 0.39, 0.47, 0.065, 0.05)
                    c = blend(c, gloss, cov * 0.45)

                    # Leaf-stem (small cute leaves)
                    c = blend(c, stem_d, capsule_cov(px, py, (0.5, 0.258), (0.5, 0.21), 0.026))
                    c = blend(c, stem, capsule_cov(px, py, (0.5, 0.245), (0.43, 0.215), 0.02))
                    c = blend(c, stem, capsule_cov(px, py, (0.5, 0.245), (0.57, 0.215), 0.02))

                    # Small horns (cuter, shorter)
                    c = blend(c, horn, capsule_cov(px, py, (0.445, 0.43), (0.40, 0.295), 0.055))
                    c = blend(c, horn, capsule_cov(px, py, (0.555, 0.43), (0.60, 0.295), 0.055))

                    # Mouth: small frown
                    cov = ellipse_cov(px, py, 0.5, 0.665, 0.075, 0.035)
                    c = blend(c, dark, cov)
                    c = blend(c, tongue, ellipse_cov(px, py, 0.5, 0.673, 0.026, 0.013))

                    # Big cute eyes
                    c = blend(c, white, circle_cov(px, py, 0.41, 0.56, 0.055))
                    c = blend(c, white, circle_cov(px, py, 0.59, 0.56, 0.055))
                    c = blend(c, dark, circle_cov(px, py, 0.425, 0.565, 0.020))
                    c = blend(c, dark, circle_cov(px, py, 0.575, 0.565, 0.020))
                    c = blend(c, white, circle_cov(px, py, 0.429, 0.559, 0.007))
                    c = blend(c, white, circle_cov(px, py, 0.571, 0.559, 0.007))

                    # Angry brows (slanted inward)
                    c = blend(c, dark, capsule_cov(px, py, (0.35, 0.495), (0.45, 0.528), 0.024))
                    c = blend(c, dark, capsule_cov(px, py, (0.65, 0.495), (0.55, 0.528), 0.024))

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