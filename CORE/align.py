# SPDX-License-Identifier: Apache-2.0
"""Match edited paragraphs back to the geometry recognised from the page.

The text the user typed is the only source of truth. Geometry follows the text,
never the other way round: if a paragraph was rewritten, the words change and the
box stays; if a paragraph was deleted, its box goes with it.

Two rules drive the implementation:

* Per-paragraph similarity with a monotonic pointer, **not** the opcode blocks of
  ``SequenceMatcher``. When two adjacent paragraphs are both edited, the opcodes
  merge them into one ``replace`` span and every box after it shifts by one.
* **Text is never dropped.** A paragraph that matches nothing still gets written;
  it takes the nearest unused source slot, or lands below its predecessor.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

from .model import Box, Line, box_of
from .segment import paragraphs_to_text

SIMILARITY_THRESHOLD = 0.25
FALLBACK_GAP = 12
FALLBACK_WIDTH = 600


@dataclass(frozen=True, slots=True)
class Placement:
    text: str
    box: Box
    matched: bool
    source_index: int | None


def _text_of(paragraph: Sequence[Line]) -> str:
    return paragraphs_to_text([paragraph])


def align(
    edited: Sequence[str],
    paragraphs: Sequence[Sequence[Line]],
    *,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[Placement]:
    """Give every edited paragraph a box, in the user's order."""
    if not edited:
        return []

    texts = [t.strip() for t in edited]
    sources = [_text_of(p) for p in paragraphs]
    n = len(paragraphs)

    used = [False] * n
    cursor = 0
    out: list[Placement] = []
    previous: Box | None = None

    for index, text in enumerate(texts):
        # Best match inside the window, not the first one over the line. Short
        # Chinese paragraphs share punctuation, so the first candidate above the
        # threshold is often the wrong one; the highest ratio keeps the pointer
        # monotonic without that failure.
        chosen = None
        best_ratio = 0.0
        for j in range(cursor, n):
            if used[j]:
                continue
            ratio = SequenceMatcher(None, text, sources[j]).ratio()
            if ratio > best_ratio:
                best_ratio, chosen = ratio, j
        if best_ratio < threshold:
            chosen = None

        if chosen is None:
            # Nearest unused slot by ordinal position, searching forward first so
            # that a deleted middle paragraph does not shift everything up.
            order = list(range(index, n)) + list(range(0, index))
            for j in order:
                if not used[j]:
                    chosen = j
                    break

        is_last = index == len(texts) - 1

        if chosen is None:
            box = (
                Box(previous.left, previous.bottom + FALLBACK_GAP, FALLBACK_WIDTH, 0)
                if previous is not None
                else Box(0, 0, FALLBACK_WIDTH, 0)
            )
            out.append(Placement(text=text, box=box, matched=False, source_index=None))
            previous = box
            continue

        used[chosen] = True
        cursor = chosen + 1
        boxes = [box_of(paragraphs[chosen])]

        if is_last:
            # Deleting blank lines merges paragraphs, so the last edited paragraph
            # absorbs the source paragraphs that *follow* it. It must not reach
            # backwards: a paragraph the user deleted earlier in the page would
            # otherwise stretch this box upwards over content that is gone.
            for j in range(chosen + 1, n):
                if not used[j]:
                    used[j] = True
                    boxes.append(box_of(paragraphs[j]))

        box = Box.union_of(boxes)
        out.append(
            Placement(
                text=text,
                box=box,
                matched=SequenceMatcher(None, text, sources[chosen]).ratio() >= threshold,
                source_index=chosen,
            )
        )
        previous = box

    return out
