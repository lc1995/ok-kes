"""章鱼眼部模板路径与加载，覆盖源码目录和 PyInstaller 冻结布局。"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import octopus_detection


class TestOctopusDetection(unittest.TestCase):
    def tearDown(self):
        octopus_detection._templates.cache_clear()

    def test_repo_template_loads(self):
        path = octopus_detection._template_file()
        self.assertTrue(path.is_file(), path)
        templates = octopus_detection._templates()
        self.assertGreater(len(templates), 0)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertIsNone(octopus_detection.match_octopus(None))
        self.assertIsNotNone(octopus_detection.match_octopus(frame))

    def test_frozen_layout_uses_ok_tasks_assets(self):
        source = octopus_detection._template_file()
        with tempfile.TemporaryDirectory() as tmp:
            mei = Path(tmp)
            dest = mei / "ok_tasks" / "assets"
            dest.mkdir(parents=True)
            shutil.copy(source, dest / "octopus_eye.png")
            fake_module = mei / "octopus_detection.py"
            fake_module.write_text("", encoding="utf-8")
            with patch.object(octopus_detection.sys, "_MEIPASS", str(mei), create=True), \
                    patch.object(octopus_detection, "__file__", str(fake_module)):
                found = octopus_detection._template_file()
            self.assertEqual(found, dest / "octopus_eye.png")
