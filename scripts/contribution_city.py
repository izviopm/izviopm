#!/usr/bin/env python3
"""Render the last year of GitHub contributions as an animated isometric city SVG (stdlib only)."""
import json
import math
import os
import random
import sys
import urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
  }
}
"""

TILE_W, TILE_H = 24, 12
MARGIN_X, MARGIN_TOP = 24, 180
# Fixed seed: same data gives the same city, so the file only changes when contributions do.
SEED = 2026
GROUND = "#161b22"
LIT = "#cfe8ff"
# Neon blue ramp, dim to bright, one colour per building level.
LEVELS = ["#0b3d91", "#1f6feb", "#388bfd", "#79c0ff"]
STYLE = """
.t{animation:tw 3s ease-in-out infinite}
.t2{animation:tw 3s ease-in-out -1s infinite}
.t3{animation:tw 3s ease-in-out -2s infinite}
.f{animation:fl 5s steps(2) infinite}
.b{animation:bl 1.5s steps(2) infinite}
@keyframes tw{50%{opacity:.2}}
@keyframes fl{50%{opacity:.15}}
@keyframes bl{50%{opacity:0}}
"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        sys.exit(f"GitHub API error: {body['errors']}")
    return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def shade(hex_color, factor):
    channels = (int(hex_color[i:i + 2], 16) * factor for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(min(255, round(v)) for v in channels)


def poly(points, fill, cls=""):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    extra = f' class="{cls}"' if cls else ""
    return f'<polygon points="{pts}" fill="{fill}"{extra}/>'


def windows(p0, p1, z, base, rng):
    """Window quads on a front face running from p0 (left) to p1 (right), up to height z."""
    def at(u, h):
        return (p0[0] + u * (p1[0] - p0[0]), p0[1] + u * (p1[1] - p0[1]) - h)

    out = []
    h0 = 6
    while h0 + 5 <= z - 3:
        for col in range(2):
            u0 = 0.12 + col * 0.46
            u1 = u0 + 0.28
            if rng.random() < 0.4:
                fill = LIT
                cls = "f" if rng.random() < 0.15 else ""
            else:
                fill, cls = shade(base, 0.35), ""
            out.append(poly([at(u0, h0), at(u1, h0), at(u1, h0 + 4), at(u0, h0 + 4)], fill, cls))
        h0 += 8
    return out


def building(x0, y0, z, base, rng):
    top = (x0, y0)
    right = (x0 + TILE_W / 2, y0 + TILE_H / 2)
    bottom = (x0, y0 + TILE_H)
    left = (x0 - TILE_W / 2, y0 + TILE_H / 2)

    def up(p):
        return (p[0], p[1] - z)

    return [
        poly([left, bottom, up(bottom), up(left)], shade(base, 0.6)),
        poly([bottom, right, up(right), up(bottom)], shade(base, 0.8)),
        *windows(left, bottom, z, base, rng),
        *windows(bottom, right, z, base, rng),
        poly([up(top), up(right), up(bottom), up(left)], base),
    ]


def render(calendar):
    rng = random.Random(SEED)
    weeks = calendar["weeks"]
    cols, rows = len(weeks), 7
    days = [(c, d) for c, week in enumerate(weeks) for d in week["contributionDays"]]
    peak = max((d["contributionCount"] for _, d in days), default=0) or 1
    width = 2 * MARGIN_X + (cols + rows) * TILE_W / 2
    height = MARGIN_TOP + (cols + rows) * TILE_H / 2 + 20
    ox = MARGIN_X + rows * TILE_W / 2  # x of the top corner of cell (0, 0)

    # Sky first, so buildings sit in front of it.
    sky = []
    # Jittered grid: one star per cell, so the sky is spread evenly instead of clumping.
    cell = 34
    for gx in range(int(width // cell) + 1):
        for gy in range(int((MARGIN_TOP - 30) // cell) + 1):
            if rng.random() < 0.7:
                x, y = gx * cell + rng.uniform(0, cell), gy * cell + rng.uniform(0, cell)
                cls = rng.choice(["t", "t2", "t3"])
                sky.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rng.choice([0.6, 1, 1.4]):.1f}" fill="#e6edf3" class="{cls}"/>')
    moon = [f'<circle cx="{width - 70:.0f}" cy="60" r="18" fill="#e6edf3"/>',
            f'<circle cx="{width - 63:.0f}" cy="54" r="16" fill="#0d1117"/>']
    plane_x, plane_y = width * 0.35, 96
    plane = [
        f'<g transform="translate({plane_x:.0f},{plane_y:.0f}) scale(0.8)">',
        # Top-down airliner, nose to the right; the red light on the top wingtip blinks.
        '<path d="M22,0 L8,-2.5 L4,-2.5 L-6,-16 L-10,-16 L-6,-2.5 L-18,-2.5 L-22,-8 L-25,-8 L-22,0 L-25,8 L-22,8 L-18,2.5 L-6,2.5 L-10,16 L-6,16 L4,2.5 L8,2.5 Z" fill="#e6edf3"/>',
        '<circle cx="-10" cy="-16" r="1.6" fill="#ff5f56" class="b"/>',
        '<circle cx="-10" cy="16" r="1.6" fill="#7ee787"/>',
        "</g>",
    ]

    ground, blocks = [], []
    # Painter's order: cells further from the viewer (smaller col + row) first.
    for c, d in sorted(days, key=lambda cd: cd[0] + cd[1]["weekday"]):
        r, count = d["weekday"], d["contributionCount"]
        x0 = ox + (c - r) * TILE_W / 2
        y0 = MARGIN_TOP + (c + r) * TILE_H / 2
        if count == 0:
            ground.append(poly([(x0, y0), (x0 + TILE_W / 2, y0 + TILE_H / 2),
                                (x0, y0 + TILE_H), (x0 - TILE_W / 2, y0 + TILE_H / 2)], GROUND))
            continue
        z = 8 + 110 * math.sqrt(count / peak)  # square root keeps quiet days visible
        base = LEVELS[min(3, int(count / peak * 4))]
        blocks.append(building(x0, y0, z, base, rng))

    total = calendar["totalContributions"]
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}">',
        f"<style>{STYLE}</style>",
        f'<rect width="100%" height="100%" fill="#0d1117"/>',
        *sky,
        *moon,
        *plane,
        f'<text x="{MARGIN_X}" y="34" font-family="monospace" font-size="18" fill="#79c0ff">contribution city</text>',
        f'<text x="{MARGIN_X}" y="56" font-family="monospace" font-size="13" fill="#8b949e">'
        f"{total} contributions in the last year</text>",
        *ground,
    ]
    body += [shape for block in blocks for shape in block]
    body.append("</svg>")
    return "\n".join(body) + "\n"


def main():
    token = os.environ["GH_TOKEN"]
    login = os.environ.get("GH_USER", "izviopm")
    out = sys.argv[1] if len(sys.argv) > 1 else "contribution-city.svg"
    calendar = fetch(login, token)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(calendar))
    print(f"wrote {out}: {calendar['totalContributions']} contributions")


if __name__ == "__main__":
    main()
