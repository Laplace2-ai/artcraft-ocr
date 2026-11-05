# SPDX-License-Identifier: Apache-2.0
"""The engine contract.

``CORE`` states what an OCR backend must produce; it does not know which backend
runs. The concrete one lives in ``ADAPTERS/`` and is the only place that imports
an OCR library, which keeps this package testable without models on disk.

Keeping it this way also keeps the packaging fix in one place: rapidocr imports
its stage modules by short name after putting its own directory on ``sys.path``,
which resolves to an empty namespace package once frozen. That aliasing belongs
to the adapter, not scattered through the core.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from .model import Line


@runtime_checkable
class Ocr(Protocol):
    """Anything that turns an image into lines."""

    def run(self, image: object) -> list[Line]:
        """Recognise every line in ``image``.

        ``image`` is whatever the adapter accepts — a path, a PIL image or a
        numpy array. The returned lines are in reading order (see
        :func:`normalize`), and nothing is filtered: a low score is still a line
        the user may want, and dropping it here would make the loss invisible.
        """
        ...


def normalize(lines: Sequence[Line]) -> list[Line]:
    """Sort into reading order: top to bottom, then left to right.

    Recognition returns lines in detection order, which is roughly but not
    reliably reading order. Sorting here means every later stage can assume it,
    instead of each one re-deriving it and disagreeing at the edges.
    """
    return sorted(lines, key=lambda ln: (ln.y, ln.x))


def keep_all(lines: Sequence[Line]) -> list[Line]:
    """Low-confidence lines stay. Present so the intent is testable.

    The rule exists because a line the recogniser is unsure about is often a line
    the user cares about — a stamp, a signature, a badly printed date. Hiding it
    turns a visible imperfection into a silent omission.
    """
    return list(lines)
