#!/usr/bin/env python3
"""Generate FocusFlow app icons using only stdlib.

Produces:
  icon-192.png         - manifest icon
  icon-512.png         - manifest icon + maskable
  apple-touch-icon.png - iOS home screen icon (180x180, opaque)

Design: dark indigo gradient background, dim track circle,
bright indigo gradient ring, solid white play triangle. Fully opaque.
"""
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


def clamp(v):
    return max(0, min(255, int(round(v))))


def mix(c1, c2, t):
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(3))


def smooth(edge, dist):
    """1.0 inside, 0.0 outside, 1px antialiasing band."""
    return max(0.0, min(1.0, (edge - dist) + 0.5))


def make_icon(size):
    # Colors
    bg_top = (49, 46, 129)     # indigo-900
    bg_bot = (15, 23, 42)      # slate-900
    track = (51, 65, 85)       # slate-700
    ring_top = (165, 180, 252) # indigo-300
    ring_bot = (99, 102, 241)  # indigo-500
    play = (255, 255, 255)

    corner = 0.22 * size
    cx = cy = 0.5 * size
    r_outer = 0.38 * size          # stays inside 80% maskable safe zone
    r_inner = 0.29 * size
    r_track = 0.40 * size

    # Play triangle (pointing right)
    tx1, ty1 = 0.37 * size, 0.41 * size
    tx2, ty2 = 0.37 * size, 0.59 * size
    tx3, ty3 = 0.59 * size, 0.50 * size

    def edge(p, q, x, y):
        return (x - p[0]) * (q[1] - p[1]) - (y - p[1]) * (q[0] - p[0])

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            acc = [0.0, 0.0, 0.0]
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    px = x + sx
                    py = y + sy

                    # Background: rounded rect (opaque everywhere is fine,
                    # corners simply show bg color)
                    bg = mix(bg_top, bg_bot, py / size)

                    # Track circle
                    dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                    track_aa = smooth(r_track, dist)
                    r, g, b = bg
                    if track_aa > 0:
                        t = track_aa
                        r = r + (track[0] - r) * t
                        g = g + (track[1] - g) * t
                        b = b + (track[2] - b) * t

                    # Bright ring
                    ring_aa = min(smooth(r_outer, dist), smooth(dist, r_inner))
                    if ring_aa > 0:
                        ring_col = mix(ring_top, ring_bot, py / size)
                        t = ring_aa
                        r = r + (ring_col[0] - r) * t
                        g = g + (ring_col[1] - g) * t
                        b = b + (ring_col[2] - b) * t

                    # Play triangle
                    e1 = edge((tx1, ty1), (tx2, ty2), px, py)
                    e2 = edge((tx2, ty2), (tx3, ty3), px, py)
                    e3 = edge((tx3, ty3), (tx1, ty1), px, py)
                    if e1 >= 0 and e2 >= 0 and e3 >= 0:
                        r, g, b = play

                    acc[0] += r
                    acc[1] += g
                    acc[2] += b
            row.append((clamp(acc[0] / 4), clamp(acc[1] / 4), clamp(acc[2] / 4)))
        rows.append(row)
    return rows


if __name__ == "__main__":
    for s, name in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        write_png(name, s, make_icon(s))
        print(f"{name} ({s}x{s}) generated")