#!/usr/bin/env python3
"""Render the last year of GitHub contributions as an isometric city SVG (stdlib only)."""
import json
import math
import os
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

TILE_W, TILE_H = 12, 6
MARGIN_X, MARGIN_TOP = 20, 90
GROUND = "#161b22"
# Neon blue ramp, dim to bright, one colour per building level.
LEVELS = ["#0b3d91", "#1f6feb", "#388bfd", "#79c0ff"]


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


def poly(points, fill):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}"/>'


def render(calendar):
    days = [(c, d) for c, week in enumerate(calendar["weeks"]) for d in week["contributionDays"]]
    peak = max((d["contributionCount"] for _, d in days), default=0) or 1
    ox = 7 * TILE_W / 2 + MARGIN_X  # x of column 0, row 0
    height = MARGIN_TOP + (len(calendar["weeks"]) + 7) * TILE_H / 2 + 20
    width = ox + len(calendar["weeks"]) * TILE_W / 2 + TILE_W + MARGIN_X
    shapes = []
    # Painter's order: cells further from the viewer (smaller col + row) first.
    for c, d in sorted(days, key=lambda cd: cd[0] + cd[1]["weekday"]):
        r, count = d["weekday"], d["contributionCount"]
        x0 = ox + (c - r) * TILE_W / 2
        y0 = MARGIN_TOP + (c + r) * TILE_H / 2
        top = (x0, y0)
        right = (x0 + TILE_W / 2, y0 + TILE_H / 2)
        bottom = (x0, y0 + TILE_H)
        left = (x0 - TILE_W / 2, y0 + TILE_H / 2)
        if count == 0:
            shapes.append(poly([top, right, bottom, left], GROUND))
            continue
        z = 4 + 4 * math.sqrt(count)  # building height follows the day's count
        base = LEVELS[min(3, int(count / peak * 4))]
        up = lambda p: (p[0], p[1] - z)
        shapes.append(poly([left, bottom, up(bottom), up(left)], shade(base, 0.6)))
        shapes.append(poly([bottom, right, up(right), up(bottom)], shade(base, 0.8)))
        shapes.append(poly([up(top), up(right), up(bottom), up(left)], base))
    total = calendar["totalContributions"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}">\n'
        f'<rect width="100%" height="100%" fill="#0d1117"/>\n'
        f'<text x="{MARGIN_X}" y="34" font-family="monospace" font-size="16" fill="#e6edf3">'
        f'contribution city</text>\n'
        f'<text x="{MARGIN_X}" y="56" font-family="monospace" font-size="12" fill="#8b949e">'
        f'{total} contributions in the last year</text>\n'
        + "\n".join(shapes)
        + "\n</svg>\n"
    )


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
