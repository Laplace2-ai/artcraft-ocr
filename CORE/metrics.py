# SPDX-License-Identifier: Apache-2.0
"""Font size estimate from a recognised line box.

Measured against the detector on 2026-11-04, by drawing text at a known point
size, recognising it, and reading the box back:

| Text | Point size | Detector box height |
|---|---|---|
| CJK, 10 chars | 14 | 17 px |
| CJK, 10 chars | 60 | 69 px |
| Latin capitals | 14 | 13 px |

The detector's box is the *line box*, not the ink: for CJK it is about 1.18 × the
point size (the line includes leading), for all-caps Latin about 0.93 × (no
descenders). Dividing by those numbers recovers the size. A single ratio was the
bug — it made every CJK line about 20 % too large, which is exactly the "small
text comes out too big" report, and it made Latin slightly too small.

This is the size that gets written; the user can still correct it per paragraph.
"""

from __future__ import annotations

from .model import Line

CJK_RATIO = 1.18
LATIN_RATIO = 0.93
MIN_SIZE = 6


def _looks_cjk(text: str) -> bool:
    """CJK dominates this line, so its box height follows the CJK ratio."""
    letters = [c for c in text if not c.isspace()]
    if not letters:
        return False
    wide = sum(1 for c in letters if "\u2e80" <= c <= "\u9fff" or "\uff00" <= c <= "\uffef")
    return wide / len(letters) >= 0.3


def estimate_size(line: Line) -> int:
    """Rough point size for a line, from its box height and its script."""
    if line.h <= 0:
        return MIN_SIZE
    ratio = CJK_RATIO if _looks_cjk(line.text) else LATIN_RATIO
    return max(MIN_SIZE, round(line.h / ratio))


# -- how wide will this text be? ------------------------------------------------

# Only used to size a paragraph frame. The host re-sets the text in the font we
# name, so measuring the same font here is the closest estimate available without
# asking the host to lay it out for us.
_FONT_FILES = {
    "Microsoft YaHei": ("msyh.ttc", "msyh.ttf"),
    "Microsoft YaHei UI": ("msyh.ttc", "msyh.ttf"),
    "SimSun": ("simsun.ttc",),
    "SimHei": ("simhei.ttf",),
    "Arial": ("arial.ttf",),
    "Times New Roman": ("times.ttf",),
}

_font_cache: dict[tuple[str, int], object] = {}


def _font_path(name: str) -> str | None:
    from pathlib import Path

    root = Path("C:/Windows/Fonts")
    for candidate in _FONT_FILES.get(name, ()) + (name,):
        path = root / candidate
        if path.exists():
            return str(path)
    for fallback in ("msyh.ttc", "arial.ttf"):
        path = root / fallback
        if path.exists():
            return str(path)
    return None


def text_width(text: str, size: int, font_name: str = "Microsoft YaHei") -> float | None:
    """Width of one line at ``size`` px, or ``None`` when no usable font exists."""
    if not text:
        return 0.0
    path = _font_path(font_name)
    if path is None:
        return None
    key = (path, int(size))
    try:
        font = _font_cache.get(key)
        if font is None:
            from PIL import ImageFont

            font = ImageFont.truetype(path, int(size))
            _font_cache[key] = font
        return float(font.getlength(text))
    except Exception:  # noqa: BLE001 - a broken font file must not break writing
        return None


def widest_line(text: str, size: int, font_name: str = "Microsoft YaHei") -> float | None:
    """Width of the longest line, which is what decides a frame's width."""
    widths = [text_width(line, size, font_name) for line in (text or "").splitlines()]
    widths = [w for w in widths if w is not None]
    if not widths:
        return None
    return max(widths)
