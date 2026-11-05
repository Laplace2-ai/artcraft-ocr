# SPDX-License-Identifier: Apache-2.0
"""The JSON an agent reads when it cannot look at the picture.

Source: adapted from the rights holder's internal OCR tool (read 2026-11-03). The field layout, the coordinate
units and the reasoning below are that file's; this copy exists so both products
emit the same shape. One deliberate difference: the schema id is namespaced for
this product — the internal one carries an organisation name that cannot appear
in a published repository. Fields and meaning are unchanged, so a consumer that
reads one reads the other; only the ``schema`` string differs.

Why this is a module and not a few lines in the interface: this JSON is a
contract. Agents and scripts parse it, so the version, the coordinate semantics
and the units live here and never scatter into UI code.

Two decisions worth keeping:

* Every box is given twice — ``bbox`` in image pixels, ``bbox_norm`` as a 0-1
  fraction of the image. An agent that has never seen the source image can still
  rebuild the layout from the fractions.
* A colour we could not sample is ``null``, never a guess. Alignment is
  ``unknown`` for a single line: one line has no alignment to speak of, and
  calling it left-aligned quietly moves text later.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "artcraft.ocr.textdata/1"

HINTS = [
    "bbox is in image pixels with the origin at the top left; bbox_norm is the "
    "same box as a 0-1 fraction of the image width and height, for rebuilding "
    "the layout at any size.",
    "PhotoCraft text layers are positioned in px; VectorCraft uses pt "
    "(1 pt = 1 px at 72 dpi); FilmCraft captions carry time, not coordinates.",
    "align is only meaningful for a paragraph of two or more lines; a single "
    "line reports unknown, and must not be treated as left-aligned.",
    "A line whose box is null still carries its text: the user's edited text "
    "differs from what was recognised on that line, so its geometry no longer "
    "applies to it.",
]


def _norm(box: Sequence[float], size: Tuple[int, int]) -> Dict[str, float]:
    x, y, w, h = box
    iw, ih = size
    iw = iw or 1
    ih = ih or 1
    return {"x": round(x / iw, 4), "y": round(y / ih, 4),
            "w": round(w / iw, 4), "h": round(h / ih, 4)}


def guess_align(boxes: Sequence[Sequence[float]]) -> str:
    """Paragraph alignment from which edge the lines share.

    A single line returns ``"unknown"``: it has no alignment information, and
    guessing "left" there would move the text for anyone reading this file.
    """
    if len(boxes) < 2:
        return "unknown"
    lefts = [b[0] for b in boxes]
    rights = [b[0] + b[2] for b in boxes]
    centers = [b[0] + b[2] / 2 for b in boxes]
    spread = lambda v: max(v) - min(v)  # noqa: E731
    sl, sc, sr = spread(lefts), spread(centers), spread(rights)
    best = min((sl, "left"), (sc, "center"), (sr, "right"))
    # All three edges are ragged: the paragraph itself is ragged, so there is no
    # alignment to report rather than the least-bad one.
    if best[0] > max(2.0, 0.02 * max(max(rights) - min(lefts), 1)):
        return "unknown"
    return best[1]


def build_payload(*, source: str, image_size: Tuple[int, int], lang: str, model: str,
                  paragraphs: List[Dict[str, Any]], app: str = "ArtCraft OCR",
                  image_path: str = "") -> Dict[str, Any]:
    """Assemble the document.

    ``paragraphs`` items: ``{"text": str, "bbox": (x, y, w, h) | None,
    "color": "#rrggbb" | None, "font_size_px": int | None,
    "lines": [{"text", "bbox", "score", "color"}]}``.

    **bbox is always (x, y, w, h)**, matching what the host's inspector answers.
    The caller converts from (l, t, r, b); nothing here guesses a format from
    the numbers, which is the mistake that silently scales a font.
    """
    iw, ih = int(image_size[0]), int(image_size[1])
    out_paras: List[Dict[str, Any]] = []
    for i, p in enumerate(paragraphs):
        box = p.get("bbox")
        rows = p.get("lines") or []
        row_boxes = [r["bbox"] for r in rows if r.get("bbox")]
        size = p.get("font_size_px")
        if not size and row_boxes:
            size = max(6, int(round(sum(b[3] for b in row_boxes) / len(row_boxes) / 0.9)))
        out_paras.append({
            "index": i,
            "text": p.get("text", ""),
            "bbox": None if not box else {"x": int(box[0]), "y": int(box[1]),
                                          "w": int(box[2]), "h": int(box[3])},
            "bbox_norm": None if not box else _norm(box, (iw, ih)),
            "align": guess_align(row_boxes) if row_boxes else "unknown",
            "color": p.get("color"),
            "font_size_px": size,
            "line_count": max(1, p.get("text", "").count("\n") + 1),
            "lines": [{
                "text": r.get("text", ""),
                "bbox": None if not r.get("bbox") else {
                    "x": int(r["bbox"][0]), "y": int(r["bbox"][1]),
                    "w": int(r["bbox"][2]), "h": int(r["bbox"][3])},
                "bbox_norm": None if not r.get("bbox") else _norm(r["bbox"], (iw, ih)),
                "color": r.get("color"),
                "score": None if r.get("score") is None else round(float(r["score"]), 4),
            } for r in rows],
        })

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": app,
        "source": {
            "name": source or "",
            "path": image_path or "",
            "width": iw,
            "height": ih,
            "lang": lang,
            "model": model,
        },
        "paragraphs": out_paras,
        "plain_text": "\n\n".join(p.get("text", "") for p in out_paras),
        "counts": {"paragraphs": len(out_paras),
                   "lines": sum(len(p["lines"]) for p in out_paras)},
        "hints": HINTS,
    }


def save(payload: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path
