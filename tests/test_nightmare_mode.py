"""噩梦开关离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))
import utils_chaos
from ChaosMode import ChaosMode


class TestNightmareMode(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.config = {"自动开启噩梦模式": True}
        self.off = np.full((720, 1280, 3), 200, dtype=np.uint8)
        self.on = np.full((720, 1280, 3), 10, dtype=np.uint8)
        self.on[int(.038 * 720):int(.056 * 720),
                int(.959 * 1280):int(.973 * 1280)] = (255, 234, 249)
        self.task.frame = self.off
        self.task.next_frame.return_value = self.on

    def handle(self, title="配置队伍"):
        with patch.object(utils_chaos, "_get_region_text", side_effect=[title, "进入"]), \
                patch.object(utils_chaos, "_move_and_click") as click:
            result = utils_chaos.handle_enable_nightmare(self.task)
        return result, click

    def test_metadata(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertTrue(mode.default_config["自动开启噩梦模式"])

    def test_disabled_and_other_pages_do_not_click(self):
        result, click = self.handle("其他页面")
        self.assertFalse(result)
        click.assert_not_called()
        self.task.config["自动开启噩梦模式"] = False
        result, click = self.handle()
        self.assertFalse(result)
        click.assert_not_called()

    def test_off_clicks_once_and_confirms(self):
        result, click = self.handle()
        self.assertTrue(result)
        click.assert_called_once()
        self.task.next_frame.assert_called_once()
        self.task.executor.pause.assert_not_called()

    def test_on_does_not_toggle(self):
        self.task.frame = self.on
        result, click = self.handle()
        self.assertFalse(result)
        click.assert_not_called()

    def test_failed_toggle_pauses_without_retry(self):
        self.task.next_frame.return_value = self.off
        result, click = self.handle()
        self.assertTrue(result)
        click.assert_called_once()
        self.task.executor.pause.assert_called_once()

    def test_unknown_does_not_click_or_enter(self):
        self.task.frame = np.zeros_like(self.off)
        self.task.next_frame.return_value = None
        result, click = self.handle()
        self.assertTrue(result)
        click.assert_not_called()
        self.task.executor.pause.assert_called_once()

    def test_pending_check_precedes_generic_handlers(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        mode.ocr = Mock(return_value=[])
        handler = Mock()
        with patch.object(utils_chaos, "handle_octopus_handoff", return_value=False), \
                patch.object(utils_chaos, "handle_enable_nightmare", return_value=True), \
                patch.object(utils_chaos, "PAGE_HANDLERS", [handler]):
            mode.run()
        handler.assert_not_called()


if __name__ == "__main__":
    unittest.main()
