# SPDX-License-Identifier: Apache-2.0
"""Integration test: real OCR through the real adapter.

Skipped when rapidocr is not installed, so the pure tests stay runnable on a
machine with no models. The page is generated here rather than committed: a
fixture image is easy to read but impossible to review, and a generated one
keeps the test self-contained.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import rapidocr_onnxruntime  # noqa: F401
    HAVE_OCR = True
except ImportError:
    HAVE_OCR = False

if HAVE_OCR:
    from PIL import Image, ImageDraw, ImageFont

    from ADAPTERS.rapidocr_engine import RapidOcrEngine
    from CORE.segment import group_paragraphs, paragraphs_to_text

# Absolute system-font paths on purpose: the test renders a page, and a CJK face is
# needed to do it. These are Windows system files, not project or machine paths, and
# every candidate is existence-checked — if none is present the test skips instead of
# failing. Whitelisted in the internal-context scan for that reason.
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def _font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise unittest.SkipTest("no CJK font available to render the test page")


@unittest.skipUnless(HAVE_OCR, "rapidocr not installed")
class RapidOcrIntegrationTests(unittest.TestCase):
    def test_page_becomes_paragraphs(self):
        img = Image.new("RGB", (900, 420), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        big, body = _font(34), _font(24)
        draw.text((40, 30), "第一章　潮汐与月亮", font=big, fill=(20, 20, 20))
        draw.text((40, 110), "潮汐是月亮写在海面上的字，它每隔十二小时重复一次。", font=body, fill=(200, 30, 30))
        draw.text((40, 140), "却从不完全一样，就像同一句话被不同的人说出来。", font=body, fill=(200, 30, 30))
        draw.text((40, 250), "我们记录它的节奏，是为了在混乱里找到可依赖的那一段规律。", font=body, fill=(0, 90, 200))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.png"
            img.save(path)
            lines = RapidOcrEngine().run(str(path))

        self.assertGreaterEqual(len(lines), 4, "the four rendered lines must be found")

        paragraphs = group_paragraphs(lines)
        self.assertEqual(len(paragraphs), 3, "heading, one wrapped paragraph, one paragraph")

        text = paragraphs_to_text(paragraphs)
        self.assertEqual(text.count("\n\n"), 2)
        self.assertIn("潮汐是月亮写在海面上的字", text)

    def test_accepts_a_pil_image(self):
        """The engine itself refuses PIL objects; the adapter must convert."""
        img = Image.new("RGB", (400, 120), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "直接传 PIL 图", font=_font(26), fill=(0, 0, 0))

        lines = RapidOcrEngine().run(img)

        self.assertTrue(lines, "a PIL image must be accepted, not rejected")

    def test_colour_survives_the_pipeline(self):
        """Red body text must sample as red, not as black."""
        from CORE.color import colors_for
        import numpy as np

        img = Image.new("RGB", (600, 160), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 40), "这是一行红色的字", font=_font(28), fill=(200, 30, 30))

        lines = RapidOcrEngine().run(np.array(img))
        self.assertTrue(lines)

        colours = colors_for(np.array(img), lines)
        sampled = [c for c in colours if c]
        self.assertTrue(sampled, "at least one line must yield a colour")
        r, g, b = (int(sampled[0][i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(r, g + 60, "red channel must dominate the sampled colour")


if __name__ == "__main__":
    unittest.main(verbosity=2)
