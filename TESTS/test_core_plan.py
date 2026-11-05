# SPDX-License-Identifier: Apache-2.0
"""What gets written, decided without a running host.

Every rule here exists because it went wrong once: 点文字 sent the recognised
lines instead of the edited ones, a chosen size was multiplied by nothing while
the box was scaled, and a paragraph's picked colour was overridden by a checkbox.
"""

from __future__ import annotations

import unittest

from CORE.model import Line
from CORE.plan import plan_items


def line(text, x=100, y=200, w=300, h=90, score=0.9):
    return Line(text=text, x=x, y=y, w=w, h=h, score=score)


class LineModeTests(unittest.TestCase):
    def test_edited_text_is_what_gets_written(self):
        origin = [[line("原文")]]
        items, _ = plan_items([{"text": "改过"}], origin, {})
        self.assertEqual(items[0][0], "改过")

    def test_edited_line_keeps_its_slot_in_the_paragraph_box(self):
        origin = [[line("一", x=50, y=10, w=100, h=20), line("二", x=50, y=40, w=100, h=20)]]
        para = {"text": "改1\n改2", "box": [50, 10, 100, 60], "lines": 2}
        items, _ = plan_items([para], origin, {})
        self.assertEqual([i[0] for i in items], ["改1", "改2"])
        # Slot arithmetic, not the recognised boxes: the text no longer matches.
        self.assertAlmostEqual(items[0][1].top, 10, places=3)
        self.assertAlmostEqual(items[1][1].top, 40, places=3)

    def test_unchanged_line_keeps_the_recognised_box(self):
        origin = [[line("原文", x=800, y=232, w=472, h=64)]]
        items, _ = plan_items([{"text": "原文"}], origin, {})
        self.assertEqual(items[0][1].left, 800)
        self.assertEqual(items[0][1].width, 472)

    def test_edited_text_with_no_geometry_is_stacked(self):
        items, _ = plan_items([{"text": "手打"}, {"text": "第二段"}], [], {})
        self.assertGreater(items[1][1].top, items[0][1].top)

    def test_line_count_comes_from_the_edited_text(self):
        origin = [[line("一段长句")]]
        items, _ = plan_items([{"text": "拆开\n成两行"}], origin, {})
        self.assertEqual(len(items), 2)


class SizeTests(unittest.TestCase):
    def test_a_chosen_size_beats_the_global_one(self):
        origin = [[line("甲", h=90)]]
        items, used = plan_items([{"text": "甲", "size": 120, "custom_size": True}],
                                 origin, {}, forced_size=24)
        self.assertEqual(items[0][3], 120)
        self.assertTrue(used)

    def test_a_chosen_size_follows_the_scale(self):
        origin = [[line("甲", h=90)]]
        items, _ = plan_items([{"text": "甲", "size": 120, "custom_size": True}],
                              origin, {}, scale=0.8)
        self.assertEqual(items[0][3], 96)

    def test_the_global_size_follows_the_scale(self):
        items, _ = plan_items([{"text": "甲"}], [], {}, forced_size=100, scale=0.5)
        self.assertEqual(items[0][3], 50)

    def test_region_text_uses_the_same_size_rule_as_point_text(self):
        origin = [[line("甲", h=90)]]
        items, _ = plan_items([{"text": "甲", "box": [0, 0, 400, 100]}],
                              origin, {}, para_mode=True)
        self.assertEqual(items[0][3], 76)    # 90 / 1.18 — not a fixed 24

    def test_a_paragraph_with_no_source_falls_back_to_24(self):
        items, _ = plan_items([{"text": "手打"}], [], {})
        self.assertEqual(items[0][3], 24)

    def test_inserting_a_paragraph_does_not_shift_the_others(self):
        """Geometry follows the text, not the index — this is what broke sizes."""
        origin = [[line("第一段", x=10, y=10, w=200, h=40)],
                  [line("第二段", x=10, y=80, w=500, h=60)]]
        paras = [{"text": "新插入"}, {"text": "第一段"}, {"text": "第二段"}]
        items, _ = plan_items(paras, origin, {})
        by_text = {i[0]: i[1] for i in items}
        self.assertEqual(by_text["第一段"].width, 200)
        self.assertEqual(by_text["第二段"].width, 500)

    def test_sizes_are_clamped_to_6_200(self):
        items, _ = plan_items([{"text": "甲", "size": 400, "custom_size": True}], [], {})
        self.assertEqual(items[0][3], 200)
        items, _ = plan_items([{"text": "甲", "size": 1, "custom_size": True}], [], {})
        self.assertEqual(items[0][3], 6)

    def test_estimate_is_used_when_nothing_is_chosen(self):
        origin = [[line("甲", h=90)]]
        items, _ = plan_items([{"text": "甲"}], origin, {})
        self.assertEqual(items[0][3], 76)    # 90 / 1.18


class ColourTests(unittest.TestCase):
    def test_following_the_ink_uses_the_sampled_colour(self):
        ink_line = line("甲")
        items, _ = plan_items([{"text": "甲"}], [[ink_line]], {id(ink_line): "#b31244"})
        self.assertEqual(items[0][2], "#b31244")

    def test_a_custom_colour_wins_over_the_checkbox_being_off(self):
        origin = [[line("甲")]]
        items, _ = plan_items([{"text": "甲", "colour": "#2e3192", "custom_colour": True}],
                              origin, {}, follow=False)
        self.assertEqual(items[0][2], "#2e3192")

    def test_without_follow_or_custom_the_default_applies(self):
        origin = [[line("甲")]]
        items, _ = plan_items([{"text": "甲", "colour": "#2e3192"}], origin, {},
                              follow=False, default_colour="#000000")
        self.assertEqual(items[0][2], "#000000")

    def test_a_lone_line_is_not_fitted_to_the_box_width(self):
        """The detector box is loose in both axes: width fitting inflated 28 pt to 38 pt."""
        origin = [[line("小字", w=300, h=20)]]
        items, _ = plan_items([{"text": "小字"}], origin, {})
        self.assertFalse(items[0][4])

    def test_a_multi_line_paragraph_is_not_fitted(self):
        origin = [[line("一", h=90)]]
        items, _ = plan_items([{"text": "一\n二"}], origin, {})
        self.assertFalse(items[0][4])

    def test_region_frame_is_wider_than_the_ink(self):
        """The host re-sets the text in its own font; the frame needs headroom.

        Frames sized to the exact ink width wrapped a word early and clipped the
        last line — reported as "the frames are mostly too short".
        """
        origin = [[line("甲", h=90)]]
        items, _ = plan_items([{"text": "甲", "box": [10, 0, 400, 100]}], origin, {},
                              para_mode=True)
        target = items[0][1]
        self.assertAlmostEqual(target.left, 10.0, places=3)
        self.assertGreater(target.width, 400.0)
        self.assertLess(target.width, 480.0)

    def test_a_longer_edited_paragraph_widens_the_frame(self):
        """The frame follows the edited text, not the recognised text.

        Editing a short caption into a long sentence used to leave the frame at
        the old width, so the host wrapped early and clipped the tail.
        """
        origin = [[line("甲", h=90)]]
        short, _ = plan_items([{"text": "甲", "box": [0, 0, 200, 100]}], origin, {},
                              para_mode=True)
        long, _ = plan_items(
            [{"text": "这是一句比原来长很多的说明文字，长到必须把框加宽才放得下整行",
              "box": [0, 0, 200, 100]}], origin, {}, para_mode=True)
        self.assertGreater(long[0][1].width, short[0][1].width * 1.5)

    def test_an_edit_shorter_than_the_ink_keeps_the_ink_width(self):
        origin = [[line("甲", h=90)]]
        items, _ = plan_items([{"text": "甲", "box": [0, 0, 400, 100]}], origin, {},
                              para_mode=True)
        self.assertGreaterEqual(items[0][1].width, 400.0)

    def test_region_mode_has_no_width_fitting(self):
        origin = [[line("甲")]]
        items, _ = plan_items([{"text": "甲", "box": [0, 0, 400, 100]}], origin, {},
                              para_mode=True)
        self.assertFalse(items[0][4])


if __name__ == "__main__":
    unittest.main()
