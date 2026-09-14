"""Operator Amber terminal theme.

Bloomberg / air-traffic-control register: warm slate-black ground, amber chrome,
cyan for derived numbers, green/rose only where the book needs a functional
bid/ask read. Contrast does the work; no decorative color.

Truecolor ANSI (24-bit). Degrades to plain text when the stream isn't a TTY or
NO_COLOR is set, so piping to a file stays clean.
"""
from __future__ import annotations

import os
import sys


def supports_unicode(stream=None) -> bool:
    """Windows consoles often default to cp1252, which can't encode block glyphs."""
    stream = stream or sys.stdout
    enc = getattr(stream, "encoding", None) or "utf-8"
    try:
        "▸█─│●▏".encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


class Glyphs:
    """Box/block glyphs with an ASCII fallback so the board survives cp1252."""

    def __init__(self, unicode_ok: bool | None = None) -> None:
        self.ok = supports_unicode() if unicode_ok is None else unicode_ok
        if self.ok:
            self.blocks = "▏▎▍▌▋▊▉█"
            self.arrow, self.rule, self.pipe, self.dot = "▸", "─", "│", "●"
        else:
            self.blocks = "=" * 7 + "#"
            self.arrow, self.rule, self.pipe, self.dot = ">", "-", "|", "*"


def supports_color(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def _fg(hexcode: str) -> str:
    h = hexcode.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\x1b[38;2;{r};{g};{b}m"


class Theme:
    """Operator Amber tokens. `enabled=False` makes every token an empty string."""

    # Two palettes. Dark is the terminal default. Light exists because a capture
    # embedded in a README sits on a light page, and the dark steps do not survive
    # the move: on warm paper (#f7f3e9) amber lands at 2.88 against a 3.0 floor.
    PALETTES = {
        "dark": dict(amber="#f59e0b", bright="#fbbf24", pale="#fcd34d", cyan="#22d3ee",
                     green="#4ade80", rose="#fb7185", ink="#e7e5e4", muted="#78716c",
                     faint="#44403c", bg="#0a0a0e"),
        "light": dict(amber="#b45309", bright="#92400e", pale="#a16207", cyan="#0369a1",
                      green="#15803d", rose="#be123c", ink="#1c1917", muted="#57534e",
                      faint="#b8b0a0", bg="#f7f3e9"),
    }

    # palette (matches the house anchor)
    AMBER = "#f59e0b"
    AMBER_BRIGHT = "#fbbf24"
    AMBER_PALE = "#fcd34d"
    CYAN = "#22d3ee"       # derived data (mid, spread)
    GREEN = "#4ade80"      # live / bid side
    ROSE = "#fb7185"       # ask side
    INK = "#e7e5e4"        # primary text
    MUTED = "#78716c"      # chrome, labels
    FAINT = "#44403c"      # rules, separators

    def __init__(self, enabled: bool | None = None, unicode_ok: bool | None = None,
                 mode: str = "dark") -> None:
        self.on = supports_color() if enabled is None else enabled
        self.g = Glyphs(unicode_ok)
        self.mode = mode
        pal = self.PALETTES[mode]
        self.AMBER, self.AMBER_BRIGHT, self.AMBER_PALE = pal["amber"], pal["bright"], pal["pale"]
        self.CYAN, self.GREEN, self.ROSE = pal["cyan"], pal["green"], pal["rose"]
        self.INK, self.MUTED, self.FAINT = pal["ink"], pal["muted"], pal["faint"]
        self.BG = pal["bg"]

    def _c(self, hexcode: str, s: str, bold: bool = False) -> str:
        if not self.on:
            return s
        b = "\x1b[1m" if bold else ""
        return f"{b}{_fg(hexcode)}{s}\x1b[0m"

    def amber(self, s, bold=False):   return self._c(self.AMBER, s, bold)
    def bright(self, s, bold=False):  return self._c(self.AMBER_BRIGHT, s, bold)
    def pale(self, s, bold=False):    return self._c(self.AMBER_PALE, s, bold)
    def cyan(self, s, bold=False):    return self._c(self.CYAN, s, bold)
    def green(self, s, bold=False):   return self._c(self.GREEN, s, bold)
    def rose(self, s, bold=False):    return self._c(self.ROSE, s, bold)
    def ink(self, s, bold=False):     return self._c(self.INK, s, bold)
    def muted(self, s, bold=False):   return self._c(self.MUTED, s, bold)
    def faint(self, s, bold=False):   return self._c(self.FAINT, s, bold)
