"""界面调试截图：只在进入新界面时写入独立目录。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))
import page_debug


class FakeTask:
    def __init__(self, enabled=True, name="自动卡厄思模式"):
        self.name = name
        self.enabled_flag = enabled
        self.frame = np.zeros((12, 16, 3), dtype=np.uint8)
        self.frame[:, :] = (10, 20, 30)
        self.logs = []
        self.logger = self

    def info(self, message):
        self.logs.append(message)

    def warning(self, message):
        self.logs.append(message)

    def get_global_config(self, option):
        if option != page_debug.PAGE_DEBUG_CONFIG:
            return {}
        return {page_debug.PAGE_DEBUG_OPTION: self.enabled_flag}


def _paint(task, color):
    task.frame = np.zeros((12, 16, 3), dtype=np.uint8)
    task.frame[:, :] = color


class TestPageDebug(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root_patch = patch.object(
            page_debug, "_screenshot_root", return_value=self.directory.name
        )
        self.root_patch.start()
        self.processor_patch = patch.object(page_debug, "_screenshot_processor", return_value=None)
        self.processor_patch.start()

    def tearDown(self):
        self.processor_patch.stop()
        self.root_patch.stop()
        self.directory.cleanup()

    def pngs(self):
        return list(Path(self.directory.name).rglob("*.png"))

    def test_dispatch_stops_at_the_first_matching_page(self):
        task = FakeTask()
        calls = []

        def first(_task):
            calls.append("first")
            return False

        def second(_task):
            calls.append("second")
            return True

        def third(_task):
            calls.append("third")
            return True

        self.assertTrue(page_debug.dispatch_page_handlers(task, [first, second, third]))
        self.assertEqual(calls, ["first", "second"])
        self.assertEqual([path.parent.name for path in self.pngs()], ["second"])

    def test_switch_off_does_not_write_or_stop_handlers(self):
        task = FakeTask(enabled=False)
        called = []

        def handle_shop(current):
            called.append(current)
            return True

        self.assertTrue(page_debug.dispatch_page_handlers(task, [handle_shop]))
        self.assertEqual(called, [task])
        self.assertEqual(self.pngs(), [])

    def test_saves_pre_click_frame_once_per_page_in_separate_directory(self):
        task = FakeTask()
        seen = {}

        def handle_shop(current):
            seen.setdefault("during", current.frame.copy())
            _paint(current, (9, 9, 9))
            return True

        self.assertTrue(page_debug.dispatch_page_handlers(task, [handle_shop]))
        self.assertTrue(page_debug.dispatch_page_handlers(task, [handle_shop]))
        files = self.pngs()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].parent.name, "handle_shop")
        self.assertEqual(files[0].parent.parent.name, "自动卡厄思模式")
        self.assertNotIn("screenshots", files[0].parts[-4:-1])
        image = cv2.imdecode(np.fromfile(files[0], dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertTrue(np.array_equal(image[0, 0], np.array([10, 20, 30], dtype=np.uint8)))
        self.assertTrue(np.array_equal(seen["during"][0, 0], np.array([10, 20, 30], dtype=np.uint8)))
        self.assertTrue(any("handle_shop" in message for message in task.logs))

    def test_page_change_and_distinct_unknown_screens_are_saved(self):
        task = FakeTask()

        def handle_shop(_task):
            return True

        def handle_rest(_task):
            return True

        def unknown(_task):
            return False

        page_debug.dispatch_page_handlers(task, [handle_shop])
        _paint(task, (200, 200, 200))
        page_debug.dispatch_page_handlers(task, [handle_rest])
        _paint(task, (0, 0, 255))
        page_debug.dispatch_page_handlers(task, [unknown])
        _paint(task, (0, 0, 250))
        page_debug.dispatch_page_handlers(task, [unknown])
        _paint(task, (255, 0, 0))
        page_debug.dispatch_page_handlers(task, [unknown])

        names = sorted(path.parent.name for path in self.pngs())
        self.assertEqual(names.count("handle_shop"), 1)
        self.assertEqual(names.count("handle_rest"), 1)
        self.assertEqual(names.count(page_debug.UNRECOGNIZED_PAGE), 2)

    def test_save_failure_does_not_stop_the_page(self):
        task = FakeTask()

        def handle_shop(_task):
            return True

        with patch.object(page_debug.cv2, "imencode", side_effect=RuntimeError("disk")):
            self.assertTrue(page_debug.dispatch_page_handlers(task, [handle_shop]))
        self.assertEqual(self.pngs(), [])
        self.assertTrue(any("保存失败" in message for message in task.logs))

    def test_processor_is_applied_before_saving(self):
        def mark(frame):
            frame[0, 0] = (0, 255, 0)
            return frame

        task = FakeTask()
        with patch.object(page_debug, "_screenshot_processor", return_value=mark):
            page_debug.dispatch_page_handlers(task, [lambda _task: True])
        image = cv2.imdecode(np.fromfile(self.pngs()[0], dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertTrue(np.array_equal(image[0, 0], np.array([0, 255, 0], dtype=np.uint8)))

    def test_missing_config_and_non_boolean_values_stay_off(self):
        task = FakeTask()
        task.get_global_config = Mock(side_effect=RuntimeError("missing"))
        self.assertFalse(page_debug.page_debug_enabled(task))
        task.get_global_config = lambda _option: Mock()
        self.assertFalse(page_debug.page_debug_enabled(task))

    def test_reenable_captures_the_current_page_again(self):
        task = FakeTask()
        page_debug.dispatch_page_handlers(task, [lambda _task: True])
        page_debug.reset_page_debug(task)
        page_debug.dispatch_page_handlers(task, [lambda _task: True])
        self.assertEqual(len(self.pngs()), 2)

    def test_frozen_build_uses_executable_directory(self):
        self.root_patch.stop()
        try:
            with patch.object(page_debug.sys, "frozen", True, create=True), \
                    patch.object(page_debug.sys, "executable", r"D:\games\ok-kes.exe"):
                self.assertEqual(
                    page_debug._screenshot_root(),
                    os.path.abspath(os.path.join(r"D:\games", page_debug.PAGE_SCREENSHOT_DIR)),
                )
        finally:
            self.root_patch.start()

    def test_global_config_registers_the_switch_off_by_default(self):
        from src.config import config
        option = next(item for item in config["global_configs"] if item.name == page_debug.PAGE_DEBUG_CONFIG)
        self.assertIs(option.default_config[page_debug.PAGE_DEBUG_OPTION], False)
        self.assertIn("page_screenshots", option.description)


if __name__ == "__main__":
    unittest.main()
