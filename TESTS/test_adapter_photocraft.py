# SPDX-License-Identifier: Apache-2.0
"""PhotoCraft adapter — the parts that can be tested without the application.

The bridge is replaced by a fake that records commands, so the placement loop and
the anchor arithmetic are exercised without launching anything. The live round
trip is covered separately by running the adapter against a real instance.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.model import Box
from ADAPTERS.photocraft import (
    BridgeError,
    PhotoCraft,
    Written,
    anchor_offset,
    box_from_corners,
    box_from_rect,
)


class BoundsFormatTests(unittest.TestCase):
    def test_two_layouts_describe_the_same_layer(self):
        """The measured case: one layer, two formats, different numbers."""
        from_corners = box_from_corners([700, 280, 798, 304])
        from_rect = box_from_rect([700, 280, 98, 24])

        self.assertEqual(from_corners.left, from_rect.left)
        self.assertEqual(from_corners.top, from_rect.top)
        self.assertAlmostEqual(from_corners.width, from_rect.width)
        self.assertAlmostEqual(from_corners.height, from_rect.height)

    def test_reading_a_corner_list_as_a_rect_is_wrong(self):
        """Guard against the mistake, not just the happy path."""
        wrong = box_from_rect([700, 280, 798, 304])
        self.assertGreater(wrong.width, 700, "798 is an x1, not a width")


class FakeBridge:
    def __init__(self, widths=None, fail_texts=(), canvas=(1920, 1080)):
        self.calls: list[tuple[str, dict]] = []
        self._widths = list(widths or [])
        self._fail = set(fail_texts)
        self._canvas = canvas
        self._layers: dict[int, Box] = {}
        self._next = 1

    def call(self, tool, arguments=None):
        self.calls.append((tool, arguments or {}))
        if tool == "doc_inspect":
            return {
                "width": self._canvas[0],
                "height": self._canvas[1],
                "layers": [
                    {"id": lid, "bounds": [b.left, b.top, b.width, b.height]}
                    for lid, b in self._layers.items()
                ],
            }
        return None

    def command(self, command_id, params=None):
        params = params or {}
        self.calls.append((command_id, params))
        if command_id == "type.create":
            if params.get("text") in self._fail:
                raise BridgeError("host said no")
            width = self._widths.pop(0) if self._widths else params["size"] * 7.34
            lid = self._next
            self._next += 1
            if "box" in params:      # paragraph text is placed by frame
                bx, by, bw, bh = params["box"]
                box = Box(bx, by, bw, bh)
            else:                     # point text is placed by baseline
                box = Box(params["x"], params["y"] - params["size"] * 0.86, width, params["size"])
            self._layers[lid] = box
            return {"layer": lid, "bounds": [box.left, box.top, box.right, box.bottom]}
        if command_id == "type.setStyle":
            lid = params["layer"]
            b = self._layers[lid]
            self._layers[lid] = Box(b.left, b.top, params["size"] * 7.34, b.height)
            return {}
        if command_id == "layer.translate":
            lid = params["layer"]
            b = self._layers[lid]
            self._layers[lid] = Box(b.left + params["dx"], b.top + params["dy"], b.width, b.height)
            return {}
        return {}


class PlaceTests(unittest.TestCase):
    def test_width_shortfall_triggers_one_resize(self):
        bridge = FakeBridge(widths=[521])
        pc = PhotoCraft(bridge)
        target = Box(800, 232, 472, 64)

        pc.place("测试", target, size=71, font="Microsoft YaHei", color="#ffffff")

        resized = [c for c in bridge.calls if c[0] == "type.setStyle"]
        self.assertEqual(len(resized), 1)
        self.assertLess(resized[0][1]["size"], 71)

    def test_translate_lands_on_the_target(self):
        bridge = FakeBridge(widths=[472])
        pc = PhotoCraft(bridge)
        target = Box(800, 232, 472, 64)

        layer = pc.place("测试", target, size=64, font="F", color="#000000")
        moved = bridge._layers[layer]

        # layer.translate takes integers, so a +/-1px residual is the contract,
        # not a defect. Assert that, not pixel equality.
        self.assertLessEqual(abs(moved.left - 800), 1)
        self.assertLessEqual(abs(moved.top - 232), 1)


class PreflightTests(unittest.TestCase):
    def test_dead_channel_is_reported_as_such(self):
        """'No document' and 'channel dead' must not be confused.

        Creating a document over a dead channel fails anyway, and the error then
        blames the document.
        """
        class DeadBridge(FakeBridge):
            def call(self, tool, arguments=None):
                if tool == "doc_inspect":
                    return {}
                if tool == "session_list":
                    raise BridgeError("no answer")
                return super().call(tool, arguments)

        pc = PhotoCraft(DeadBridge())
        self.assertFalse(pc.session_ok())
        with self.assertRaises(BridgeError):
            pc.ensure_document()


class SizeAndModeTests(unittest.TestCase):
    def _run(self, **kwargs):
        bridge = FakeBridge(widths=[1200])
        pc = PhotoCraft(bridge)
        pc.place("测试", Box(100, 100, 300, 40), size=24, font="F", color="#000", **kwargs)
        resized = len([c for c in bridge.calls if c[0] == "type.setStyle"])
        created = [c for c in bridge.calls if c[0] == "type.create"][0][1]
        return resized, created

    def test_estimated_size_is_fitted_to_the_box(self):
        resized, created = self._run()
        self.assertGreater(resized, 0, "auto size should be reconciled with the box")
        self.assertIn("x", created, "point text is placed by baseline")

    def test_a_size_the_user_chose_is_not_fitted(self):
        """Fitting would overwrite it — the reverse-fit undoes the choice."""
        resized, _ = self._run(force_size=True)
        self.assertEqual(resized, 0)

    def test_paragraph_mode_uses_a_frame(self):
        resized, created = self._run(paragraph=True)
        self.assertEqual(resized, 0)
        self.assertIn("box", created)
        self.assertNotIn("x", created)


class RefusalTests(unittest.TestCase):
    def test_a_string_answer_is_an_error_not_a_result(self):
        """The host refuses with a plain string, e.g. when no document is open.

        Passing that on produced 'string indices must be integers' three frames
        later, which pointed at the wrong place entirely.
        """
        class RefusingBridge(FakeBridge):
            def command(self, command_id, params=None):
                if command_id == "type.create":
                    return "no document open"
                return super().command(command_id, params)

        pc = PhotoCraft(RefusingBridge())
        with self.assertRaises(BridgeError):
            pc.place("x", Box(0, 0, 10, 10), size=12, font="F", color="#000")


class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Box(0, 0, 1000, 500)
        self.items = [("a", Box(100, 100, 200, 50))]

    def test_original_position_does_not_move(self):
        self.assertEqual(anchor_offset(self.items, self.canvas, "原位置"), (0, 0))

    def test_top_left(self):
        self.assertEqual(anchor_offset(self.items, self.canvas, "左上"), (-100, -100))

    def test_bottom_right(self):
        dx, dy = anchor_offset(self.items, self.canvas, "右下")
        self.assertEqual(dx, 700)   # 100 -> 800
        self.assertEqual(dy, 350)   # 100 -> 450

    def test_items_with_extra_fields_still_align(self):
        """Options are appended to items; alignment must not depend on arity.

        This broke exactly once: adding colour and size to every item made
        unpacking two names fail with 'too many values to unpack'.
        """
        detailed = [("a", Box(100, 100, 200, 50), "#000000", 24)]
        self.assertEqual(anchor_offset(detailed, self.canvas, "左上"), (-100, -100))

    def test_centre(self):
        dx, dy = anchor_offset(self.items, self.canvas, "中心")
        self.assertEqual(dx, (1000 - 200) // 2 - 100)
        self.assertEqual(dy, (500 - 50) // 2 - 100)


class PartialFailureTests(unittest.TestCase):
    def test_stops_after_three_consecutive_failures(self):
        items = [("x", Box(0, 0, 10, 10))] * 6
        bridge = FakeBridge(fail_texts={"x"})
        pc = PhotoCraft(bridge)

        results = pc.place_all(items, size=12, font="F", color="#000000")

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.error for r in results))

    def test_keeps_going_past_an_isolated_failure(self):
        items = [("ok", Box(0, 0, 10, 10)), ("bad", Box(0, 20, 10, 10)), ("ok", Box(0, 40, 10, 10))]
        bridge = FakeBridge(fail_texts={"bad"})
        pc = PhotoCraft(bridge)

        results = pc.place_all(items, size=12, font="F", color="#000000")

        self.assertEqual(len(results), 3)
        self.assertIsNone(results[0].error)
        self.assertIsNotNone(results[1].error)
        self.assertIsNone(results[2].error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
