# SPDX-License-Identifier: Apache-2.0
"""One recognised text line, as the engine and every later stage see it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Line:
    """A single detected line of text.

    Coordinates are pixels in the source image, ``x``/``y`` being the top-left of
    the line's box. ``score`` comes from the recogniser and is carried through
    unchanged: a low score is still a line the user may want, so nothing here
    drops it.
    """

    text: str
    x: int
    y: int
    w: int
    h: int
    score: float = 1.0

    @property
    def center_y(self) -> float:
        return self.y + self.h / 2

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


@dataclass(frozen=True, slots=True)
class Box:
    """A rectangle in image pixels, top-left origin.

    Deliberately not a list or tuple: the host applications return two different
    array layouts (``[x0,y0,x1,y1]`` from ``type.create`` and ``[x,y,w,h]`` from
    ``doc_inspect``), and reading the wrong one silently scales the font instead
    of raising. Adapters convert once, at their boundary; nothing downstream ever
    sees an array.
    """

    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @classmethod
    def union_of(cls, boxes: "list[Box]") -> "Box":
        left = min(b.left for b in boxes)
        top = min(b.top for b in boxes)
        right = max(b.right for b in boxes)
        bottom = max(b.bottom for b in boxes)
        return cls(left, top, right - left, bottom - top)


def box_of(lines: "Sequence[Line]") -> Box:
    return Box.union_of([Box(ln.x, ln.y, ln.w, ln.h) for ln in lines])
