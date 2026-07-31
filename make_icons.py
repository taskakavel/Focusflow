#!/usr/bin/env python3
"""Generate FocusFlow app icons (192x192 and 512x512 PNG) using only stdlib."""
import struct
import zlib


def chunk(tag, data):
    c = tag + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))


def write_png(path, size, pixels):
    """pixels: list of rows, each row a list of (r,g,b,a) tuples."""
    raw = b""
    for row in pixels:
        raw += b"\x00"  # filter type 0
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))
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
    """1.0 inside, 0.0 outside, with 1px AA band."""
    return max(0.0, min(1.0, (edge - dist) + 0.5))


def make_icon(size):
    # Colors
    bg_top = (30, 27, 75)      # #1e1b4b
    bg_bot = (15, 23, 42)      # #0f172a
    ring_top = (129, 140, 248) # #818cf8
    ring_bot = (79, 70, 229)   # #4f46e5
    play = (255, 255, 255)

    corner = 0.20 * size
    cx = 0.50 * size
    cy = 0.50 * size
    r_outer = 0.46 * size
    ring_w = 0.09 * size
    r_inner = r_outer - ring_w

    # Play triangle vertices (pointing right)
    tx1, ty1 = 0.42 * size, 0.40 * size
    tx2, ty2 = 0.42 * size, 0.62 * size
    tx3, ty3 = 0.64 * size, 0.51 * size

    def edge(p, q, x, y):
        return (x - p[0]) * (q[1] - p[1]) - (y - p[1]) * (q[0] - p[0])

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            # 2x2 supersampling for antialiasing
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    px = x + sx
                    py = y + sy

                    # Rounded-rect background
                    rx = min(px, size - px)
                    ry = min(py, size - py)
                    if rx < corner and ry < corner:
                        d_corner = ((corner - rx) ** 2 + (corner - ry) ** 2) ** 0.5
                        alpha_bg = smooth(corner, d_corner)
                    else:
                        alpha_bg = 1.0

                    if alpha_bg <= 0:
                        continue
                    bg = mix(bg_top, bg_bot, py / size)

                    # Ring
                    dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                    ring_aa = min(smooth(r_outer, dist), smooth(dist, r_inner))
                    ring_col = mix(ring_top, ring_bot, py / size)

                    # Play triangle
                    e1 = edge((tx1, ty1), (tx2, ty2), px, py)
                    e2 = edge((tx2, ty2), (tx3, ty3), px, py)
                    e3 = edge((tx3, ty3), (tx1, ty1), px, py)
                    in_tri = e1 >= 0 and e2 >= 0 and e3 >= 0
                    play_aa = 1.0 if in_tri else 0.0

                    # Composite: bg -> ring -> play
                    r, g, b = bg
                    a = alpha_bg
                    if ring_aa > 0:
                        t = ring_aa * alpha_bg
                        r = r + (ring_col[0] - r) * t
                        g = g + (ring_col[1] - g) * t
                        b = b + (ring_col[2] - b) * t
                        a = a + (1 - a) * t
                    if play_aa > 0:
                        t = play_aa * alpha_bg
                        r = r + (play[0] - r) * t
                        g = g + (play[1] - g) * t
                        b = b + (play[2] - b) * t
                        a = a + (1 - a) * t

                    acc[0] += r
                    acc[1] += g
                    acc[2] += b
                    acc[3] += a
            n = 4.0
            row.append((
                clamp(acc[0] / n),
                clamp(acc[1] / n),
                clamp(acc[2] / n),
                clamp(acc[3] / n),
            ))
        rows.append(row)
    return rows


if __name__ == "__main__":
    for s in (192, 512):
        write_png(f"icon-{s}.png", s, make_icon(s))
        print(f"icon-{s}.png generated")