# SPDX-License-Identifier: Apache-2.0
"""Ink colour per line.

The line box already tells us where the text is; the question is which colour the
text itself was drawn in. Sampling the darkest pixel is wrong — antialiasing and
compression produce near-black speckle at glyph edges. Instead the modal colour of
the box is treated as paper, everything far enough from it as ink, and the ink is
summarised by the median of its darkest quarter.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .model import Line

BACKGROUND_DISTANCE = 90
MIN_INK_PIXELS = 12
CORE_FRACTION = 0.25


def _otsu(values: np.ndarray) -> float:
    """Otsu threshold of a 0-255 array, computed on a 256-bin histogram."""
    hist, _ = np.histogram(values, bins=256, range=(0, 256))
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 128.0
    omega = np.cumsum(hist) / total
    mu = np.cumsum(hist * np.arange(256)) / total
    mu_t = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma = (mu_t * omega - mu) ** 2 / (omega * (1 - omega))
    sigma = np.nan_to_num(sigma, nan=-1.0, posinf=-1.0, neginf=-1.0)
    return float(np.argmax(sigma))


def page_paper(rgb: np.ndarray) -> np.ndarray:
    """Mean colour of a thin border ring — the closest thing to "the paper".

    Only used to decide *which* of the two luminance clusters is the background.
    The majority rule cannot do that: a 70 px heading with heavy strokes measured
    51 % ink inside its own box, and picking the bigger side returned the paper as
    the ink colour.
    """
    h, w = rgb.shape[:2]
    pad = max(2, min(h, w) // 100)
    ring = np.concatenate([
        rgb[:pad].reshape(-1, 3), rgb[-pad:].reshape(-1, 3),
        rgb[:, :pad].reshape(-1, 3), rgb[:, -pad:].reshape(-1, 3),
    ]).astype(np.float32)
    return ring.mean(axis=0)


def sample_line(rgb: np.ndarray, line: Line, paper_hint: np.ndarray | None = None) -> str | None:
    """Ink colour of one line as ``#rrggbb``, or ``None`` when there is too little ink.

    ``None`` is a real answer: the caller falls back to a default colour rather
    than inventing one from noise.

    The split is by **luminance, two clusters**, not by "the modal colour is the
    paper". That assumption breaks exactly where it matters: a 70 px display
    heading covers a fair share of its own box, and on a textured poster no single
    colour is common enough to stand for the paper at all. Measured on the bronze
    poster, the modal colour inside the BRONZE box was the ink (4 % of pixels), so
    the "ink" the old rule picked was the paper — #b6aea5 for black type.

    Ink is whichever side of the split has fewer pixels; its colour is the median
    of the quarter furthest from the other cluster, which favours glyph cores over
    their antialiased rims.
    """
    h, w = rgb.shape[:2]
    x0 = max(0, min(line.x, w))
    y0 = max(0, min(line.y, h))
    x1 = max(x0, min(line.right, w))
    y1 = max(y0, min(line.bottom, h))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None

    crop = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    if crop.size == 0:
        return None

    luminance = crop @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    # _otsu returns a histogram bin, not a continuous value: a pixel at 80.8
    # lands in bin 80, so comparing against the bin index alone puts it on the
    # wrong side and the "ink" side comes back empty.
    threshold = _otsu(luminance) + 1.0
    dark = crop[luminance <= threshold]
    light = crop[luminance > threshold]
    if len(dark) < MIN_INK_PIXELS or len(light) < MIN_INK_PIXELS:
        # Otsu can put everything on one side of a very flat histogram; a median
        # split is a worse threshold but it always produces two sides.
        threshold = float(np.median(luminance))
        dark = crop[luminance <= threshold]
        light = crop[luminance > threshold]
    if len(dark) < MIN_INK_PIXELS or len(light) < MIN_INK_PIXELS:
        return None

    if paper_hint is None:
        paper_hint = page_paper(rgb)
    # Which cluster is the page? The one that looks like the border, not the one
    # with more pixels — heavy display type can outnumber the paper inside its box.
    dark_gap = float(np.abs(dark.mean(axis=0) - paper_hint).sum())
    light_gap = float(np.abs(light.mean(axis=0) - paper_hint).sum())
    ink, paper = (dark, light) if light_gap <= dark_gap else (light, dark)
    if len(ink) * 100 > len(crop) * 92:
        # Almost nothing but ink: a filled block or a box that missed the glyphs.
        # Refusing beats returning a colour that is really the paper.
        return None

    paper_mean = paper.mean(axis=0)
    distance = np.abs(ink - paper_mean).sum(axis=1)
    if float(distance.max()) < BACKGROUND_DISTANCE:
        return None

    cut = np.percentile(distance, (1.0 - CORE_FRACTION) * 100)
    core = ink[distance >= cut]
    if len(core) == 0:
        core = ink

    r, g, b = np.median(core, axis=0).astype(int)
    return f"#{r:02x}{g:02x}{b:02x}"


def colors_for(rgb: np.ndarray, lines: Sequence[Line]) -> list[str | None]:
    hint = page_paper(rgb)
    return [sample_line(rgb, line, hint) for line in lines]
