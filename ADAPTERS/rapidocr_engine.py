# SPDX-License-Identifier: Apache-2.0
"""rapidocr backend for the CORE engine contract.

This is the only module in the project that imports an OCR library. Everything
else depends on ``CORE.engine.Ocr``, which is why the core can be tested with no
models on disk.

Two things here are non-obvious and are the reason this file exists at all:

* **Frozen builds.** rapidocr appends its own package directory to ``sys.path``
  and then imports its stage modules by short name (``ch_ppocr_v3_det``). Once
  packaged, that directory holds no ``.py`` files, so the name resolves to an
  empty namespace package and the class lookup fails. The aliases below are not
  defensive programming — without them the built app dies on startup.
* **Flat kwargs.** Model paths are passed as ``det_model_path`` / ``rec_model_path``
  / ``cls_model_path``, not nested under ``Det``/``Rec``. Passing a nested dict
  is silently ignored and the bundled models are used instead, which looks like
  "the wrong language model" rather than "the argument was dropped".
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from CORE.model import Line

DEFAULT_SCORE = 0.5


def _alias_frozen_imports() -> None:
    """Map rapidocr's short module names onto the bundled subpackages."""
    try:
        import rapidocr_onnxruntime.ch_ppocr_v2_cls as cls_mod
        import rapidocr_onnxruntime.ch_ppocr_v3_det as det_mod
        import rapidocr_onnxruntime.ch_ppocr_v3_rec as rec_mod
    except ImportError:  # running from source; the real modules resolve normally
        return
    for name, module in (
        ("ch_ppocr_v3_det", det_mod),
        ("ch_ppocr_v3_rec", rec_mod),
        ("ch_ppocr_v2_cls", cls_mod),
    ):
        sys.modules.setdefault(name, module)


class RapidOcrEngine:
    """Turns an image into :class:`Line` objects."""

    def __init__(
        self,
        rec_model_path: str | None = None,
        det_model_path: str | None = None,
        cls_model_path: str | None = None,
        text_score: float = DEFAULT_SCORE,
    ) -> None:
        _alias_frozen_imports()
        from rapidocr_onnxruntime import RapidOCR

        kwargs: dict[str, object] = {"text_score": text_score}
        for key, value in (
            ("rec_model_path", rec_model_path),
            ("det_model_path", det_model_path),
            ("cls_model_path", cls_model_path),
        ):
            if value is not None:
                if not Path(value).exists():
                    raise FileNotFoundError(f"{key} not found: {value}")
                kwargs[key] = value

        self._ocr = RapidOCR(**kwargs)

    def run(self, image: object) -> list[Line]:
        """Recognise an image.

        Accepts a path, ``bytes``, a numpy array or a PIL image. The engine
        rejects PIL objects outright, so they are converted here — a detail worth
        keeping in one place rather than at every call site.
        """
        if hasattr(image, "mode") and hasattr(image, "convert"):
            import numpy as np

            image = np.array(image.convert("RGB"))

        scale = self._upscale_for_small_text(image)
        if scale > 1:
            import numpy as np
            from PIL import Image

            big = Image.fromarray(image).resize(
                (image.shape[1] * scale, image.shape[0] * scale), Image.LANCZOS
            )
            result, _elapsed = self._ocr(np.array(big))
            lines = self._to_lines(result or [])
            # Coordinates belong to the caller's image, not to the enlarged copy.
            return [
                Line(text=l.text, x=int(round(l.x / scale)), y=int(round(l.y / scale)),
                     w=max(1, int(round(l.w / scale))), h=max(1, int(round(l.h / scale))),
                     score=l.score)
                for l in lines
            ]

        result, _elapsed = self._ocr(image)
        return self._to_lines(result or [])

    @staticmethod
    def _upscale_for_small_text(image: object) -> int:
        """Factor to enlarge a small image by before recognition.

        A crop of one or two characters is often only a few dozen pixels tall,
        and the detector's minimum height discards it — the result is "nothing
        recognised" on an image that clearly has text. Enlarging first puts the
        glyphs back above that floor.
        """
        try:
            height = int(getattr(image, "shape")[0])
        except Exception:
            return 1
        if height <= 0:
            return 1
        target = 220
        if height >= target // 2:
            return 1
        return max(2, min(6, target // max(1, height)))

    @staticmethod
    def _to_lines(result: Sequence[Sequence[object]]) -> list[Line]:
        """Convert ``[[box, text, score], ...]`` into lines.

        rapidocr gives each box as four corner points; the rest of the project
        works in top-left plus size, so the conversion happens exactly once,
        here.
        """
        lines: list[Line] = []
        for item in result:
            if len(item) < 2:
                continue
            box, text = item[0], str(item[1])
            score = float(item[2]) if len(item) > 2 and item[2] is not None else 1.0

            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            x0, y0 = min(xs), min(ys)
            lines.append(
                Line(
                    text=text,
                    x=int(round(x0)),
                    y=int(round(y0)),
                    w=int(round(max(xs) - x0)),
                    h=int(round(max(ys) - y0)),
                    score=score,
                )
            )
        return lines
