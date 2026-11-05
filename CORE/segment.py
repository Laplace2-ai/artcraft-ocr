# SPDX-License-Identifier: Apache-2.0
"""Line → block → paragraph, and paragraph → plain text.

All distances are expressed in ``unit``, the **median** line height of the page.
A mean would be dragged upwards by headings, which is precisely the case where
the geometry has to stay right: a heading is taller than the body it labels.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Sequence

from .model import Line

SAME_LINE_CENTER_TOLERANCE = 0.5
BLOCK_GAP = 1.2
# Inter-line gap that still counts as one paragraph, in multiples of the median
# line height. Sensitive to leading: a page set with very loose leading produces
# a gap above this and gets split per line. The value follows the engine spec and
# has not been calibrated against real documents yet — when it is, this is the
# number to change, and the reason to change it is a page that splits wrongly.
PARAGRAPH_GAP = 0.75
PARAGRAPH_INDENT = 1.2


def unit_of(lines: Sequence[Line]) -> float:
    """Median line height. Never zero, so callers can divide by it."""
    heights = [ln.h for ln in lines if ln.h > 0]
    if not heights:
        return 1.0
    return max(1.0, float(statistics.median(heights)))


def _is_latin(ch: str) -> bool:
    return ch.isascii() and ch.isalpha()


def _is_word_char(ch: str) -> bool:
    """Latin letters and digits are words; CJK is set without spaces at the seam."""
    return ch.isascii() and ch.isalnum()


def join_line(left: str, right: str) -> str:
    """Join two lines of one paragraph.

    Chinese text is not spaced at the seam; two Latin words need one space or
    they merge into a different word.
    """
    if not left:
        return right
    if not right:
        return left
    if _is_word_char(left[-1]) and _is_word_char(right[0]):
        return f"{left} {right}"
    return left + right


def build_blocks(lines: Sequence[Line]) -> list[list[Line]]:
    """Split a page into visual blocks.

    A block is a run of lines on the same visual row: two columns of text sitting
    side by side on one line must not be joined into one sentence, so a wide
    horizontal gap starts a new block.
    """
    if not lines:
        return []

    unit = unit_of(lines)
    ordered = sorted(lines, key=lambda ln: (ln.center_y, ln.x))

    blocks: list[list[Line]] = []
    for line in ordered:
        if blocks:
            head = blocks[-1][0]
            same_row = abs(line.center_y - head.center_y) < SAME_LINE_CENTER_TOLERANCE * unit
            gap = line.x - blocks[-1][-1].right
            # Scale the gap against this row's own type size, not the page median.
            # A heading with a wide space in it is one line of large text; measured
            # against body-sized type the gap looks like a column break and the
            # heading splits into two paragraphs.
            local = max(head.h, line.h)
            if same_row and gap <= BLOCK_GAP * local:
                blocks[-1].append(line)
                continue
        blocks.append([line])

    for block in blocks:
        block.sort(key=lambda ln: ln.x)
    return blocks


def group_paragraphs(lines: Sequence[Line]) -> list[list[Line]]:
    """Group lines into paragraphs by vertical rhythm, type size and left edge.

    A poster is not an article. Ten separate things that happen to sit near each
    other are ten things, and merging them produces text like "TEXT2TEXT1" —
    two design elements welded into one string that the user then has to unpick
    by hand. So a paragraph continues only when all of these hold:

    * the next block starts right below the previous one (tight leading);
    * it is set at the same size — a heading and the line under it are different
      elements even when they touch;
    * it starts on the same left edge, or overlaps the previous block's width;
    * it is not the *same row*, because side-by-side columns are separate blocks.

    Returns paragraphs as lists of lines in reading order.
    """
    blocks = build_blocks(lines)
    if not blocks:
        return []

    unit = unit_of(lines)
    ordered = sorted(blocks, key=lambda b: (min(ln.center_y for ln in b),
                                            min(ln.x for ln in b)))

    paragraphs: list[list[Line]] = []
    for block in ordered:
        block.sort(key=lambda ln: ln.x)
        if paragraphs and _continues(paragraphs[-1], block, unit):
            paragraphs[-1].extend(block)
        else:
            paragraphs.append(list(block))
    return paragraphs


SIZE_TOLERANCE = 0.35


def _continues(prev: Sequence[Line], block: Sequence[Line], unit: float) -> bool:
    """Does ``block`` belong to the paragraph above it?"""
    prev_bottom = max(ln.bottom for ln in prev)
    prev_top = min(ln.y for ln in prev)
    top = min(ln.y for ln in block)

    # 并列：同一排的两块是两列文字，不是一行的延续。
    if abs(top - prev_top) < SAME_LINE_CENTER_TOLERANCE * unit:
        return False

    if top - prev_bottom > PARAGRAPH_GAP * unit:
        return False

    prev_height = statistics.median(ln.h for ln in prev)
    height = statistics.median(ln.h for ln in block)
    if abs(prev_height - height) > SIZE_TOLERANCE * max(prev_height, height):
        return False

    left_gap = abs(min(ln.x for ln in block) - min(ln.x for ln in prev))
    if left_gap > PARAGRAPH_INDENT * unit:
        return False

    # 水平方向要接得上：要么左缘对齐，要么落在上一块的范围里。
    prev_right = max(ln.right for ln in prev)
    prev_left = min(ln.x for ln in prev)
    block_left = min(ln.x for ln in block)
    block_right = max(ln.right for ln in block)
    if block_left > prev_right or block_right < prev_left:
        return False

    return True


def paragraphs_to_text(paragraphs: Iterable[Sequence[Line]]) -> str:
    """Plain text with one blank line between paragraphs."""
    out: list[str] = []
    for para in paragraphs:
        text = ""
        for line in para:
            text = join_line(text, line.text.strip())
        if text:
            out.append(text)
    return "\n\n".join(out)
