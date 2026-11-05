# SPDX-License-Identifier: Apache-2.0
"""Decide what gets written, line by line, before a host is involved.

This is the part that kept breaking: which text, at what size, in what colour,
and which box it keeps. It lives here, as a pure function, because every one of
those questions has been answered wrongly at least once.

Two rules carry most of the weight:

* **Geometry follows the text, not the position.** Matching a recognised line by
  its index in the paragraph list breaks the moment the user inserts, deletes or
  splits a paragraph — every later line then inherits the wrong box, and the
  width-fitting step turns that into a wildly wrong font size. Lines are matched
  by their own text, and each recognised line may be used once.
* **One size rule for both modes.** A frame does not make text a different size;
  it only decides where the line breaks. Using a fixed 24 pt inside frames made
  every recognised block shrink to a quarter of its size on the page.
"""

from __future__ import annotations

from typing import Sequence

from CORE.metrics import estimate_size, widest_line
from CORE.model import Box

MIN_SIZE = 6
MAX_SIZE = 200
FALLBACK_SIZE = 24


def _clamp(size: float) -> int:
    return max(MIN_SIZE, min(MAX_SIZE, int(round(size))))


def _pool(origin: Sequence[Sequence]) -> list:
    """Every recognised line, in reading order, as one list to match against."""
    return [line for paragraph in origin for line in paragraph]


def _take(pool: list, used: set[int], text: str):
    """First unused recognised line whose text is this text."""
    wanted = text.strip()
    for index, line in enumerate(pool):
        if index in used:
            continue
        if line.text.strip() == wanted:
            used.add(index)
            return line
    return None


FRAME_WIDTH_ALLOWANCE = 1.06
FRAME_WIDTH_PAD = 10.0


def plan_items(paragraphs: Sequence[dict],
               origin: Sequence[Sequence],
               colour_of: dict[int, str],
               *,
               scale: float = 1.0,
               forced_size: int = 0,
               para_mode: bool = False,
               follow: bool = True,
               default_colour: str = "#000000",
               first_top: float = 40.0,
               font: str = "Microsoft YaHei") -> tuple[list[tuple[str, Box, str, int, bool]], bool]:
    """Return ``(items, custom_size_used)``.

    Each item is ``(text, target box, colour, size, fit_width)``.

    Size: this paragraph, then the global 字号, then the size implied by the
    picture. Colour: this paragraph, then 跟随原文字色, then the default.
    """
    items: list[tuple[str, Box, str, int, bool]] = []
    pool = _pool(origin)
    used: set[int] = set()
    top = first_top
    custom_size_used = False

    for para in paragraphs:
        text = (para.get("text") or "").strip()
        if not text:
            continue
        box = para.get("box")

        def size_for(source, region: bool) -> int:
            nonlocal custom_size_used
            if para.get("custom_size") and para.get("size"):
                custom_size_used = True
                return _clamp(float(para["size"]) * scale)
            if forced_size:
                return _clamp(forced_size * scale)
            if source is not None:
                return _clamp(estimate_size(source) * scale)
            if para.get("size"):
                return _clamp(float(para["size"]) * scale)
            return _clamp(FALLBACK_SIZE * scale)

        def colour_for(source) -> str:
            if para.get("custom_colour") and para.get("colour"):
                return para["colour"]
            if follow:
                ink = colour_of.get(id(source)) if source is not None else None
                if ink:
                    return ink
                if para.get("colour"):
                    return para["colour"]
            return default_colour

        if para_mode:
            source = _take(pool, used, text.split("\n")[0])
            size = size_for(source, True)
            if box:
                # A recognised box is the *ink*, and 71 pt of ink does not fit a
                # 64 px frame: the host then drops every line past the frame,
                # which is what "the position is wrong" looked like. The frame
                # grows downwards to hold the lines; its top stays where the ink
                # was, so the text still starts where the original started.
                lines_here = max(1, text.count("\n") + 1)
                height = max(box[3], lines_here * round(size * 1.2))
                # The frame has to hold the text as it is *now*, not as it was
                # recognised: editing a paragraph to something longer used to
                # leave the frame at the old width and clip the last words.
                # Measure the longest line in the font that will be asked for,
                # and keep the detected width when it is the wider of the two.
                needed = widest_line(text, size, font) if text else None
                base = max(box[2], needed or 0.0)
                width = (base * FRAME_WIDTH_ALLOWANCE + FRAME_WIDTH_PAD) * scale
                target = Box(box[0] * scale, box[1] * scale, width, height * scale)
            else:
                target = Box(40.0, top, 0.0, 0.0)
                top += max(size * 1.8, 24)
            items.append((text, target, colour_for(source), size, False))
            continue

        # 点文字: one layer per line, each line matched to the line it came from.
        current = text.split("\n")
        for number, line_text in enumerate(current):
            if not line_text.strip():
                continue
            source = _take(pool, used, line_text)
            if source is not None:
                target = Box(source.x * scale, source.y * scale,
                             source.w * scale, source.h * scale)
                size = size_for(source, False)
            elif box:
                # Edited text: no box of its own, so it keeps the slot it had
                # inside its paragraph rather than an invented position.
                slot = max(1, len(current))
                height = box[3] / slot
                target = Box(box[0] * scale, (box[1] + number * height) * scale,
                             box[2] * scale, height * scale)
                size = size_for(None, False)
            else:
                size = size_for(None, False)
                target = Box(40.0, top, 0.0, 0.0)
                top += max(size * 1.8, 24)
            # No width fitting, in either mode. The detector box is loose in BOTH
            # dimensions — its width includes trailing space, so "fit to the box
            # width" inflated a 28 pt line to 38 pt when the box was wider than
            # the text. The height estimate (now script-aware) is the size; the
            # box's width is not consulted for it.
            items.append((line_text, target, colour_for(source), size, False))

    return items, custom_size_used
