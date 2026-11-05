# SPDX-License-Identifier: Apache-2.0
"""Behavioural tests for the engine core.

Everything here is pure: pixels and geometry in, values out. That is deliberate —
these are the rules that were wrong at some point on the internal line, and each
test names the failure it prevents.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from CORE.align import align
from CORE.color import sample_line
from CORE.convert import convert
from CORE.engine import keep_all, normalize
from CORE.metrics import estimate_size
from CORE.model import Line
from CORE.segment import build_blocks, group_paragraphs, join_line, paragraphs_to_text


def line(text: str, x: int, y: int, w: int = 200, h: int = 20, score: float = 1.0) -> Line:
    return Line(text=text, x=x, y=y, w=w, h=h, score=score)


class SegmentTests(unittest.TestCase):
    def test_two_columns_on_one_row_stay_apart(self):
        """Adjacent columns share a row but are not one sentence."""
        left = line("左边的栏", 0, 100, w=300)
        right = line("右邊的欄", 700, 100, w=300)

        blocks = build_blocks([left, right])

        self.assertEqual(len(blocks), 2, "a 400px gap must start a new block")

    def test_close_neighbours_share_a_block(self):
        a = line("前半", 0, 100, w=100)
        b = line("后半", 120, 100, w=100)

        blocks = build_blocks([a, b])

        self.assertEqual(len(blocks), 1)

    def test_heading_with_a_wide_space_stays_one_block(self):
        """A heading is one line of large type, not two columns.

        Measured against the body-size median the gap looks like a column break;
        it has to be measured against the heading's own height.
        """
        heading_a = line("第一章", 40, 36, w=103, h=35)
        heading_b = line("潮汐与月亮", 177, 39, w=168, h=32)
        body = line("潮汐是月亮写在海面上的字。", 41, 118, w=315, h=21)

        blocks = build_blocks([heading_a, heading_b, body])

        self.assertEqual(len(blocks), 2, "heading and body, not three separate blocks")

    def test_paragraph_break_on_vertical_gap(self):
        rows = [
            line("第一段第一行", 0, 100),
            line("第一段第二行", 0, 124),
            line("第二段", 0, 180),
        ]

        paragraphs = group_paragraphs(rows)

        self.assertEqual(len(paragraphs), 2)

    def test_continuous_lines_are_one_paragraph(self):
        rows = [line(f"第{i}行", 0, 100 + i * 24) for i in range(4)]

        paragraphs = group_paragraphs(rows)

        self.assertEqual(len(paragraphs), 1)


    def test_columns_on_one_row_are_two_paragraphs(self):
        """TEXT4 and TEXT5 sat on one row, 248 px apart, and came out as TEXT4TEXT5."""
        left = line("TEXT4", 51, 1046, w=73, h=25)
        right = line("TEXT5", 372, 1046, w=75, h=25)

        paragraphs = group_paragraphs([left, right])

        self.assertEqual(len(paragraphs), 2)
        self.assertEqual([p[0].text for p in paragraphs], ["TEXT4", "TEXT5"])

    def test_a_small_line_above_a_heading_is_its_own_paragraph(self):
        """TEXT2 (25 px) sat 14 px above TEXT1 (86 px) and merged into TEXT2TEXT1."""
        small = line("TEXT2", 56, 35, w=69, h=25)
        heading = line("TEXT1", 61, 74, w=310, h=86)

        paragraphs = group_paragraphs([small, heading])

        self.assertEqual(len(paragraphs), 2, "different type sizes are different blocks")

    def test_a_poster_of_separate_elements_stays_separate(self):
        """The regression that started this: ten labels, ten paragraphs."""
        rows = [
            line("TEXT2", 56, 35, w=69, h=25),
            line("TEXT1", 61, 74, w=310, h=86),
            line("TEXT3", 55, 364, w=70, h=25),
            line("TEXT4", 51, 1046, w=73, h=25),
            line("TEXT5", 372, 1046, w=75, h=25),
            line("TEXT6", 55, 1188, w=198, h=54),
            line("TEXT7", 55, 1250, w=89, h=28),
            line("TEXT8", 54, 1316, w=71, h=28),
            line("TEXT9", 55, 1396, w=59, h=24),
            line("TEXT10", 55, 1505, w=57, h=21),
        ]

        paragraphs = group_paragraphs(rows)

        self.assertEqual(len(paragraphs), 10)
        self.assertEqual([p[0].text for p in paragraphs],
                         [f"TEXT{i}" for i in (2, 1, 3, 4, 5, 6, 7, 8, 9, 10)])

    def test_heading_does_not_drag_the_unit_up(self):
        """One tall heading must not change how body lines group."""
        rows = [
            line("标题", 0, 100, h=60),
            line("正文一", 0, 200, h=20),
            line("正文二", 0, 224, h=20),
        ]

        paragraphs = group_paragraphs(rows)

        self.assertEqual(len(paragraphs), 2, "heading and body must not merge")


class JoinTests(unittest.TestCase):
    def test_chinese_seam_has_no_space(self):
        self.assertEqual(join_line("潮汐是月亮", "写在海面上"), "潮汐是月亮写在海面上")

    def test_latin_seam_gets_one_space(self):
        self.assertEqual(join_line("tidal", "rhythm"), "tidal rhythm")

    def test_a_digit_seam_is_still_a_word_seam(self):
        """TEXT4 + TEXT5 must not become TEXT4TEXT5."""
        self.assertEqual(join_line("TEXT4", "TEXT5"), "TEXT4 TEXT5")

    def test_mixed_seam_is_not_spaced(self):
        self.assertEqual(join_line("OCR 识别", "结果"), "OCR 识别结果")

    def test_paragraphs_to_text_uses_blank_line(self):
        paras = [
            [line("甲", 0, 0), line("乙", 0, 24)],
            [line("丙", 0, 80)],
        ]
        self.assertEqual(paragraphs_to_text(paras), "甲乙\n\n丙")


class ColorTests(unittest.TestCase):
    def _page(self, ink: tuple[int, int, int]) -> np.ndarray:
        """White paper with glyph-like strokes, not a solid block of ink.

        A box filled entirely with one colour has no background to measure
        against, which is a different case (and correctly returns ``None``).
        """
        page = np.full((60, 120, 3), 255, dtype=np.uint8)
        for y in range(16, 46, 10):
            page[y:y + 2, 14:106] = ink
        return page

    def test_reports_the_ink_colour(self):
        page = self._page((200, 30, 30))
        got = sample_line(page, line("x", 10, 10, w=100, h=40))
        self.assertEqual(got, "#c81e1e")

    def test_light_text_on_a_dark_page(self):
        """Dark pages are common; the ink is the bright cluster there.

        Sampling the darkest pixels on a dark page returns the antialiased rim,
        i.e. grey, which is exactly the bug this asserts against.
        """
        page = np.full((60, 120, 3), 12, dtype=np.uint8)
        for y in range(16, 46, 10):
            page[y:y + 2, 14:106] = (255, 255, 255)

        got = sample_line(page, line("x", 10, 10, w=100, h=40))

        self.assertEqual(got, "#ffffff")


    def test_heavy_ink_does_not_flip_ink_and_paper(self):
        """A display heading covers half its box; the bigger side is not the paper.

        Measured on the bronze poster: the BRONZE box was 51 % ink, and "the
        modal / bigger side is the background" returned the paper as #b6aea5.
        """
        page = np.full((200, 300, 3), 250, dtype=np.uint8)
        page[40:160, 20:280] = (20, 20, 18)
        for y in range(60, 150, 18):
            page[y:y + 3, 24:276] = 250        # gaps so it is type, not a slab

        got = sample_line(page, line("x", 24, 45, w=250, h=110))

        self.assertIsNotNone(got)
        r, g, b = (int(got[i:i + 2], 16) for i in (1, 3, 5))
        self.assertLess(max(r, g, b), 60, f"expected near-black ink, got {got}")

    def test_light_type_on_a_dark_panel(self):
        page = np.full((200, 300, 3), 18, dtype=np.uint8)
        for y in range(60, 150, 14):
            page[y:y + 4, 40:260] = (245, 240, 230)

        got = sample_line(page, line("x", 40, 50, w=220, h=110))

        self.assertIsNotNone(got)
        r, g, b = (int(got[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(min(r, g, b), 190, f"expected near-white ink, got {got}")

    def test_returns_none_when_there_is_too_little_ink(self):
        page = np.full((60, 120, 3), 255, dtype=np.uint8)
        page[10, 10] = (0, 0, 0)
        self.assertIsNone(sample_line(page, line("x", 10, 10, w=100, h=40)))

    def test_out_of_bounds_box_is_survivable(self):
        page = np.full((20, 20, 3), 255, dtype=np.uint8)
        self.assertIsNone(sample_line(page, line("x", 200, 200, w=50, h=20)))


class SizeTests(unittest.TestCase):
    def test_latin_uses_the_measured_ratio(self):
        # 14 pt all-caps Latin: the detector box is 13 px (0.93 x em).
        self.assertEqual(estimate_size(line("x", 0, 0, h=13)), 14)

    def test_cjk_uses_its_own_ratio(self):
        # 14 pt CJK: the detector box is 17 px (1.18 x em).
        self.assertEqual(estimate_size(line("凡不能精言之", 0, 0, h=17)), 14)

    def test_sizes_round(self):
        self.assertEqual(estimate_size(line("x", 0, 0, h=18)), 19)

    def test_has_a_floor(self):
        self.assertEqual(estimate_size(line("x", 0, 0, h=1)), 6)


class AlignTests(unittest.TestCase):
    def setUp(self):
        self.paragraphs = [
            [line("第一章　潮汐与月亮", 10, 100, w=400, h=30)],
            [line("潮汐是月亮写在海面上的字。", 10, 200, w=600), line("它每隔十二小时重复一次。", 10, 230, w=600)],
            [line("我们记录它的节奏。", 10, 300, w=500)],
        ]

    def test_one_character_edit_keeps_the_box(self):
        edited = ["第一章　潮汐与月亮", "潮汐是月亮写在海面上的字。它每隔十二小时重复一次。", "我们记录它的节奏。"]

        out = align(edited, self.paragraphs)

        self.assertEqual(out[0].box.top, 100)
        self.assertEqual(out[0].box.height, 30)
        self.assertTrue(out[0].matched)

    def test_merging_by_deleting_a_blank_line_takes_the_union(self):
        edited = ["第一章　潮汐与月亮", "潮汐是月亮写在海面上的字。它每隔十二小时重复一次。我们记录它的节奏。"]

        out = align(edited, self.paragraphs)

        self.assertEqual(len(out), 2)
        merged = out[1].box
        self.assertEqual(merged.top, 200)
        self.assertEqual(merged.bottom, 320, "the merged paragraph must span both source boxes")

    def test_deleting_text_removes_the_box(self):
        edited = ["第一章　潮汐与月亮", "我们记录它的节奏。"]

        out = align(edited, self.paragraphs)

        self.assertEqual(len(out), 2)
        self.assertEqual(out[1].box.top, 300)

    def test_full_rewrite_keeps_every_paragraph(self):
        """Text is never dropped, even when nothing resembles the source."""
        edited = ["完全无关的一段", "另一段也无关", "第三段同样无关"]

        out = align(edited, self.paragraphs)

        self.assertEqual([p.text for p in out], edited)
        self.assertEqual(len({p.box.top for p in out}), 3, "each paragraph needs its own slot")

    def test_empty_edit_produces_nothing(self):
        self.assertEqual(align([], self.paragraphs), [])


class EngineContractTests(unittest.TestCase):
    def test_normalize_sorts_y_then_x(self):
        scattered = [
            line("c", 300, 100),
            line("b", 100, 100),
            line("a", 100, 40),
        ]
        got = [ln.text for ln in normalize(scattered)]
        self.assertEqual(got, ["a", "b", "c"])

    def test_normalize_keeps_low_scores(self):
        weak = line("模糊的一行", 0, 0, score=0.21)
        self.assertEqual(keep_all([weak]), [weak])


class ConvertTests(unittest.TestCase):
    def test_simplified_to_traditional(self):
        out, changed = convert("汉字", "s2t")
        self.assertEqual(out, "漢字")
        self.assertEqual(changed, 1, "字 is already traditional; only 汉 changes")

    def test_round_trip(self):
        once, _ = convert("开发软件", "s2t")
        back, _ = convert(once, "t2s")
        self.assertEqual(back, "开发软件")

    def test_unknown_characters_are_left_alone(self):
        out, changed = convert("abc123", "s2t")
        self.assertEqual((out, changed), ("abc123", 0))

    def test_bad_direction_is_an_error_not_a_silent_no_op(self):
        with self.assertRaises(ValueError):
            convert("x", "sideways")


if __name__ == "__main__":
    unittest.main(verbosity=2)
