# SPDX-License-Identifier: Apache-2.0
"""The settings value may be the folder or the exe, and both must work.

Saving the full ``photocraft.exe`` path the picker shows as ``host_dir`` produced
``...\\photocraft.exe\\photocraft.exe`` — a "no photocraft.exe in that folder"
error with a path that looked corrupted. These cases pin the normalisation.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from APP.main import host_folder


class HostFolderTests(unittest.TestCase):
    def test_a_directory_is_returned_unchanged(self):
        self.assertEqual(str(host_folder(r"L:\Apps\photocraft")), r"L:\Apps\photocraft")

    def test_an_exe_path_becomes_its_directory(self):
        self.assertEqual(str(host_folder(r"L:\Apps\photocraft\photocraft.exe")),
                         r"L:\Apps\photocraft")

    def test_the_suffix_decides_even_when_the_file_is_absent(self):
        self.assertEqual(str(host_folder(r"L:\Nope\photocraft.EXE")), r"L:\Nope")

    def test_a_trailing_separator_still_means_the_directory(self):
        self.assertEqual(str(host_folder("L:/Apps/photocraft/")), r"L:\Apps\photocraft")


class ReloadTests(unittest.TestCase):
    """Refresh re-reads the file, which is the whole point of opening a PSD."""

    def setUp(self):
        import tempfile
        from APP.main import Api

        self.tmp = tempfile.mkdtemp()
        self.api = Api()
        self.path = Path(self.tmp) / "page.png"

    def test_reload_returns_the_new_file_contents(self):
        from PIL import Image

        Image.new("RGB", (20, 10), (10, 20, 30)).save(self.path)
        self.assertTrue(self.api._load_image(str(self.path))["ok"])

        Image.new("RGB", (30, 40), (200, 10, 10)).save(self.path)
        res = self.api.reload_image()

        self.assertTrue(res["ok"])
        self.assertEqual((res["width"], res["height"]), (30, 40))
        self.assertTrue(res["reloadable"])

    def test_reload_without_a_file_is_a_clear_no(self):
        self.api._image_path = ""
        res = self.api.reload_image()
        self.assertFalse(res["ok"])
        self.assertIn("error", res)

    def test_a_missing_file_is_reported_not_raised(self):
        self.api._image_path = str(Path(self.tmp) / "gone.png")
        res = self.api.reload_image()
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
