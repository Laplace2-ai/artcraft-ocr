# SPDX-License-Identifier: Apache-2.0
"""The exported JSON is a contract, so its shape is tested rather than assumed.

Three things downstream code depends on and that would fail silently if they
changed: boxes travel as (x, y, w, h), a box always comes with its 0-1 fraction,
and a colour we did not sample is null instead of a guess.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from CORE import textdata


class PayloadTests(unittest.TestCase):
    def payload(self, paragraphs, size=(1000, 500)):
        return textdata.build_payload(source="page.png", image_size=size, lang="cht",
                                      model="m.onnx", paragraphs=paragraphs)

    def test_schema_and_counts(self):
        doc = self.payload([
            {"text": "甲", "bbox": (10, 20, 100, 40), "color": "#112233",
             "font_size_px": 44, "lines": []},
            {"text": "乙\n丙", "bbox": None, "color": None, "font_size_px": None,
             "lines": [{"text": "乙", "bbox": (0, 0, 10, 10), "score": 0.9, "color": None}]},
        ])
        self.assertEqual(doc["schema"], textdata.SCHEMA)
        self.assertEqual(doc["counts"], {"paragraphs": 2, "lines": 1})
        self.assertEqual(doc["source"]["width"], 1000)
        self.assertIn("甲", doc["plain_text"])

    def test_bbox_is_width_height_not_corners(self):
        doc = self.payload([{"text": "甲", "bbox": (10, 20, 100, 40), "lines": []}])
        self.assertEqual(doc["paragraphs"][0]["bbox"],
                         {"x": 10, "y": 20, "w": 100, "h": 40})

    def test_norm_is_a_fraction_of_the_image(self):
        doc = self.payload([{"text": "甲", "bbox": (100, 50, 200, 100), "lines": []}])
        self.assertEqual(doc["paragraphs"][0]["bbox_norm"],
                         {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})

    def test_missing_geometry_stays_null(self):
        doc = self.payload([{"text": "手打的", "bbox": None, "color": None, "lines": []}])
        para = doc["paragraphs"][0]
        self.assertIsNone(para["bbox"])
        self.assertIsNone(para["bbox_norm"])
        self.assertIsNone(para["color"])
        self.assertEqual(para["text"], "手打的")

    def test_single_line_has_no_alignment(self):
        doc = self.payload([{"text": "甲", "bbox": (0, 0, 10, 10),
                             "lines": [{"text": "甲", "bbox": (5, 0, 10, 10)}]}])
        self.assertEqual(doc["paragraphs"][0]["align"], "unknown")

    def test_shared_left_edge_reads_as_left(self):
        lines = [{"text": "a", "bbox": (10, 0, 50, 10)},
                 {"text": "b", "bbox": (10, 12, 80, 10)}]
        doc = self.payload([{"text": "a\nb", "bbox": (10, 0, 80, 22), "lines": lines}])
        self.assertEqual(doc["paragraphs"][0]["align"], "left")

    def test_centred_lines_read_as_center(self):
        lines = [{"text": "a", "bbox": (30, 0, 40, 10)},
                 {"text": "b", "bbox": (10, 12, 80, 10)}]
        doc = self.payload([{"text": "a\nb", "bbox": (10, 0, 80, 22), "lines": lines}])
        self.assertEqual(doc["paragraphs"][0]["align"], "center")

    def test_ragged_lines_do_not_get_a_verdict(self):
        lines = [{"text": "a", "bbox": (0, 0, 30, 10)},
                 {"text": "b", "bbox": (90, 12, 40, 10)}]
        doc = self.payload([{"text": "a\nb", "bbox": (0, 0, 130, 22), "lines": lines}])
        self.assertEqual(doc["paragraphs"][0]["align"], "unknown")

    def test_size_falls_back_to_line_height(self):
        lines = [{"text": "a", "bbox": (0, 0, 10, 90)}, {"text": "b", "bbox": (0, 0, 10, 90)}]
        doc = self.payload([{"text": "a\nb", "bbox": (0, 0, 10, 180),
                             "font_size_px": None, "lines": lines}])
        self.assertEqual(doc["paragraphs"][0]["font_size_px"], 100)

    def test_save_writes_utf8_json(self):
        doc = self.payload([{"text": "繁體字", "bbox": (0, 0, 10, 10), "lines": []}])
        path = Path(tempfile.mkdtemp()) / "out.json"
        textdata.save(doc, str(path))
        again = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(again["paragraphs"][0]["text"], "繁體字")


if __name__ == "__main__":
    unittest.main()
