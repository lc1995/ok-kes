"""卡厄思闪光拉黑列表离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils
from ChaosMode import ChaosMode


def _box(name, x, y, width, height):
    box = SimpleNamespace(name=name, x=x, y=y, width=width, height=height)
    box.area = lambda: width * height
    return box


def _flash(name, description, x):
    return {"name": name, "description": description, "x": x, "y": 0.4}


class TestFlashBlacklist(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.name = "自动卡厄思模式"
        self.task.width = 1000
        self.task.height = 1000
        self.task.config = {
            "游戏语言": "简体中文",
            "闪光优先级": ["剑雨感应：生成2张极光剑", "剑雨赋予其回收"],
            "闪光拉黑列表": [],
            "首层刷特定闪光": False,
        }
        self.task.node_status = {"get_specific_flash": False}
        self.task.member_status = utils._initial_member_status()
        self.task.all_texts = [_box("查看原件", 850, 20, 120, 60)]
        self.high = _flash("剑雨", "感应：生成2张极光剑", 0.2)
        self.later = _flash("剑雨", "赋予其回收", 0.8)
        self.other = _flash("剑雨", "伤害次数增加", 0.5)
        click = patch.object(utils, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)
        recognize = patch.object(utils, "recognize_cards")
        self.recognize = recognize.start()
        self.addCleanup(recognize.stop)
        target = patch.object(utils, "find_target_card", return_value=([], []))
        target.start()
        self.addCleanup(target.stop)

    def _choose(self, cards):
        self.recognize.return_value = cards
        return utils.handle_view_original(self.task)

    def test_metadata_defaults_to_empty_blacklist(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertEqual(mode.default_config["闪光拉黑列表"], [])
        description = mode.config_description["闪光拉黑列表"]
        self.assertIn("不选择这个闪光", description)
        self.assertIn("闪光优先级", description)
        self.assertIn("列表为空时不启用拉黑", description)

    def test_blacklist_rejects_higher_priority_and_chooses_later(self):
        self.task.config["闪光拉黑列表"] = ["剑雨 感应 生成2张"]
        self.task.config["首层刷特定闪光"] = True
        self.assertTrue(self._choose([self.high, self.later]))
        self.click.assert_called_once_with(self.task, 0.8, 0.4)
        self.assertFalse(self.task.node_status["get_specific_flash"])

    def test_empty_blacklist_keeps_old_priority_and_random_fallback(self):
        self.task.config["首层刷特定闪光"] = True
        self.assertTrue(self._choose([self.later, self.high]))
        self.click.assert_called_once_with(self.task, 0.2, 0.4)
        self.assertTrue(self.task.node_status["get_specific_flash"])

        self.click.reset_mock()
        self.task.config["闪光优先级"] = ["展开极光安息唯一"]
        self.task.config["首层刷特定闪光"] = False
        self.recognize.return_value = [self.high, self.later]
        with patch.object(utils.random, "choice", return_value=self.later) as choice:
            self.assertTrue(utils.handle_view_original(self.task))
        choice.assert_called_once_with([self.high, self.later])
        self.click.assert_called_once_with(self.task, 0.8, 0.4)

    def test_non_matching_description_is_still_selectable(self):
        self.task.config["闪光拉黑列表"] = ["展开极光安息唯一", "极光剑生成"]
        self.assertTrue(self._choose([self.high, self.other]))
        self.click.assert_called_once_with(self.task, 0.2, 0.4)

    def test_all_blacklisted_does_not_select(self):
        self.task.config["闪光拉黑列表"] = ["剑雨"]
        with patch.object(utils.random, "choice") as choice:
            self.assertTrue(self._choose([self.high, self.later, self.other]))
        choice.assert_not_called()
        self.click.assert_not_called()

    def test_random_fallback_does_not_use_blacklisted_flash(self):
        self.task.config["闪光优先级"] = ["展开极光安息唯一"]
        self.task.config["闪光拉黑列表"] = ["生成2张极光剑"]
        self.recognize.return_value = [self.high, self.other]
        with patch.object(utils.random, "choice", return_value=self.other) as choice:
            self.assertTrue(utils.handle_view_original(self.task))
        choice.assert_called_once_with([self.other])
        self.click.assert_called_once_with(self.task, 0.5, 0.4)

    def test_sortie_ignores_shared_blacklist(self):
        self.task.name = "自动出击模式"
        self.task.config["闪光拉黑列表"] = ["剑雨感应生成2张"]
        self.assertTrue(self._choose([self.high, self.later]))
        self.click.assert_called_once_with(self.task, 0.2, 0.4)

    def test_stuck_fallback_does_not_click_blacklisted_flash(self):
        self.task.config["闪光拉黑列表"] = ["剑雨"]
        self.task._last_change_time = 0
        self.task.find_one.return_value = None
        self.recognize.return_value = [self.high, self.later]
        with patch.object(utils, "is_frame_stuck", return_value=True), patch(
            "utils_sortie.handle_secret_enemy"
        ):
            self.assertFalse(utils.handle_stuck_log(self.task))
        self.click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
