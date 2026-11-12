"""获取刷存档主战员头像：点击无反应时不能无限重试。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils_chaos


class TestSaveTargetMember(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.node_status = {"save_target_member": False}
        self.task.config = {"刷存档主战员": "蒂菲拉"}
        for name, value in (
            ("_get_current_hp_percent", 100),
            ("_get_config_value", "蒂菲拉"),
        ):
            p = patch.object(utils_chaos, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        click = patch.object(utils_chaos, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)
        clock = patch.object(utils_chaos.time, "time", return_value=1000.0)
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    def test_gives_way_after_three_clicks_then_retries_later(self):
        for _ in range(3):
            self.assertTrue(utils_chaos.handle_save_target_member(self.task))
        self.assertFalse(utils_chaos.handle_save_target_member(self.task))
        self.assertEqual(self.click.call_count, 3)

        self.clock.return_value = 1059.0
        self.assertFalse(utils_chaos.handle_save_target_member(self.task))
        self.assertEqual(self.click.call_count, 3)

        self.clock.return_value = 1061.0
        self.assertTrue(utils_chaos.handle_save_target_member(self.task))
        self.assertEqual(self.click.call_count, 4)

    def test_no_click_once_avatar_saved(self):
        self.task.node_status["save_target_member"] = True
        self.assertFalse(utils_chaos.handle_save_target_member(self.task))
        self.click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
