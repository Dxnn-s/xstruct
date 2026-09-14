"""Render an animated GIF of the live board straight from real venue data.

Not a screen recording. It polls the actual venues, captures the same ANSI the
terminal would print, then draws those frames with a mono font. The data is real;
only the rendering is synthetic.

    python tools/make_demo_gif.py --venue pascal --mode light --frames 14
"""
from __future__ import annotations

import argparse
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, ".")
from xstruct.render.board import render_board, render_header  # noqa: E402
from xstruct.render.theme import Theme  # noqa: E402

ANSI = re.compile(r"\x1b\[(?:1m)?(?:38;2;(\d+);(\d+);(\d+))?m?")
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
]


def parse_ansi(line: str, default: str):
    """Split one ANSI line into (text, hexcolor) runs."""
    runs, cur, pos = [], default, 0
    for m in re.finditer(r"\x1b\[[0-9;]*m", line):
        chunk = line[pos:m.start()]
        if chunk:
            runs.append((chunk, cur))
        code = m.group(0)
        if code == "\x1b[0m":
            cur = default
        else:
            rgb = re.search(r"38;2;(\d+);(\d+);(\d+)", code)
            if rgb:
                cur = "#%02x%02x%02x" % tuple(int(g) for g in rgb.groups())
        pos = m.end()
    tail = line[pos:]
    if tail:
        runs.append((tail, cur))
    return runs


def load_font(size: int):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_frame(text: str, theme: Theme, font, pad: int = 22, size: int = 17):
    lines = text.split("\n")
    cw = font.getbbox("M")[2] or int(size * 0.6)
    lh = int(size * 1.55)
    width = pad * 2 + cw * max((len(ANSI.sub("", l)) for l in lines), default=40)
    height = pad * 2 + lh * len(lines)
    img = Image.new("RGB", (width, height), theme.BG)
    d = ImageDraw.Draw(img)
    for row, line in enumerate(lines):
        x = pad
        for chunk, color in parse_ansi(line, theme.INK):
            d.text((x, pad + row * lh), chunk, font=font, fill=color)
            x += cw * len(chunk)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="pascal")
    ap.add_argument("--mode", default="light", choices=["light", "dark"])
    ap.add_argument("--frames", type=int, default=14)
    ap.add_argument("--markets", type=int, default=2)
    ap.add_argument("--rows", type=int, default=5)
    ap.add_argument("--out", default="assets/board-demo.gif")
    args = ap.parse_args()

    from xstruct.cli import make_venue

    theme = Theme(enabled=True, unicode_ok=True, mode=args.mode)
    font = load_font(17)
    venue = make_venue(args.venue, None)
    markets = venue.get_markets()[: args.markets]
    print(f"polling {venue.name} for {args.frames} frames across {len(markets)} markets")

    frames = []
    for i in range(args.frames):
        parts = [render_header(venue.name, len(markets), theme)]
        for m in markets:
            book = venue.get_book(m.symbol, depth=10)
            parts.append(render_board(book, market=m, theme=theme, top=args.rows))
        frames.append(render_frame("\n".join(parts), theme, font))
        print(f"  frame {i+1}/{args.frames}", end="\r")

    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    frames = [f if f.size == (w, h) else _pad(f, w, h, theme.BG) for f in frames]
    frames[0].save(args.out, save_all=True, append_images=frames[1:],
                   duration=650, loop=0, optimize=False, disposal=2)
    print(f"\nwrote {args.out}  ({w}x{h}, {len(frames)} frames)")


def _pad(img, w, h, bg):
    canvas = Image.new("RGB", (w, h), bg)
    canvas.paste(img, (0, 0))
    return canvas


if __name__ == "__main__":
    main()
