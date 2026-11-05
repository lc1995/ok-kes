"""首层装备策略离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils
import utils_chaos
from ChaosMode import ChaosMode


class TestFirstLayerStrategy(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.default_config = {}
        self.task.config = {
            "只打第一层": True,
            "首层结束策略": "目标装备达标时暂停",
            "暂停所需目标装备数量": 2,
            "装备1号位优先级": ["蚀化臂铠", "备用武器"],
            "装备2号位优先级": ["拷问工具箱"],
            "装备3号位优先级": ["异象石碑"],
        }
        self.task.node_status = {"pass_final_boss_count": 1, "success_rounds": 4}
        self.task.member_status = utils._initial_member_status()
        self.task.member_status["equipment"]["names"] = ["蚀化臂铠", "拷问工具箱", ""]
        click = patch.object(utils, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)

    def assert_escaped(self):
        self.assertTrue(utils._finish_only_first_layer(self.task))
        self.click.assert_called_once_with(self.task, 0.959, 0.051)
        self.task.executor.pause.assert_not_called()
        self.assertEqual(self.task.node_status["success_rounds"], 5)

    def test_metadata_defaults_to_escape_and_limits_count(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertEqual(mode.default_config["首层结束策略"], "自动逃离")
        self.assertEqual(mode.default_config["暂停所需目标装备数量"], 3)
        self.assertEqual(mode.config_type["暂停所需目标装备数量"], {"min": 1, "max": 3})

    def test_default_and_old_configs_still_escape_with_target_equipment(self):
        for strategy in ("自动逃离", None):
            with self.subTest(strategy=strategy):
                if strategy is None:
                    self.task.config.pop("首层结束策略")
                else:
                    self.task.config["首层结束策略"] = strategy
                self.assert_escaped()
                self.click.reset_mock()
                self.task.node_status["success_rounds"] = 4

    def test_threshold_pauses_without_clicking_or_incrementing_success(self):
        self.assertTrue(utils._finish_only_first_layer(self.task))
        self.task.executor.pause.assert_called_once()
        self.task.log_warning.assert_called_once()
        self.click.assert_not_called()
        self.assertEqual(self.task.node_status["success_rounds"], 4)
        self.assertEqual(self.task.member_status["equipment"]["names"][0], "蚀化臂铠")

    def test_more_than_required_also_pauses(self):
        self.task.config["暂停所需目标装备数量"] = 1
        self.assertTrue(utils._finish_only_first_layer(self.task))
        self.task.executor.pause.assert_called_once()
        self.click.assert_not_called()

    def test_below_threshold_escapes(self):
        self.task.config["暂停所需目标装备数量"] = 3
        self.assert_escaped()

    def test_only_current_equipment_matching_its_slot_counts(self):
        self.task.member_status["equipment"]["names"] = ["拷问工具箱", "无关装备", ""]
        self.task.config["暂停所需目标装备数量"] = 1
        self.assert_escaped()

    def test_any_priority_entry_counts_and_traditional_config_is_supported(self):
        self.task.member_status["equipment"]["names"][0] = "备用武器"
        self.task.config["装备2号位优先级"] = ["拷問工具箱"]
        self.assertTrue(utils._finish_only_first_layer(self.task))
        self.task.executor.pause.assert_called_once()

    def test_empty_priorities_do_not_count(self):
        self.task.config["装备1号位优先级"] = []
        self.task.config["装备2号位优先级"] = [""]
        self.assert_escaped()

    def test_disabled_first_layer_or_unfinished_layer_does_nothing(self):
        for first_layer, passed in ((False, 1), (True, 0)):
            with self.subTest(first_layer=first_layer, passed=passed):
                self.task.config["只打第一层"] = first_layer
                self.task.node_status["pass_final_boss_count"] = passed
                self.assertFalse(utils._finish_only_first_layer(self.task))
                self.task.executor.pause.assert_not_called()
                self.click.assert_not_called()

    def test_target_pause_takes_priority_over_missing_flash(self):
        self.task.config["首层刷特定闪光"] = True
        self.task.node_status["get_specific_flash"] = False
        self.assertTrue(utils._finish_only_first_layer(self.task))
        self.task.executor.pause.assert_called_once()
        self.click.assert_not_called()

    def test_notification_failure_still_pauses(self):
        self.task.log_warning.side_effect = RuntimeError("notification failed")
        with self.assertRaises(RuntimeError):
            utils._finish_only_first_layer(self.task)
        self.task.executor.pause.assert_called_once()
        self.click.assert_not_called()

    def test_settlement_pauses_after_optional_reward_claim(self):
        for claim_reward in (False, True):
            with self.subTest(claim_reward=claim_reward):
                self.task.config["领取奖励(只使用验证卡)"] = claim_reward
                title = SimpleNamespace(name="结算")
                with patch.object(utils_chaos, "find_box_at_point", side_effect=[title, None]):
                    self.assertTrue(utils_chaos.handle_chaos_reward_settlement(self.task))
                self.task.executor.pause.assert_called_once()
                self.task.executor.pause.reset_mock()
                self.click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
