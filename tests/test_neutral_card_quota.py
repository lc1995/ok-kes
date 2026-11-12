"""卡厄思“卡组所需中立卡牌”数量限制离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils
from ChaosMode import ChaosMode


def _card(name, x=0.4, y=0.4):
    return {"name": name, "x": x, "y": y}


class TestNeutralCardQuota(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.name = "自动卡厄思模式"
        self.task.config = {
            "游戏语言": "简体中文",
            "卡牌奖励优先级": ["梦之边境"],
            "刷初始卡牌": "环绕之光",
            "卡组所需中立卡牌": ["环绕之光*1", "梦之边境*2", "装备包"],
        }
        self.task.node_status = utils._initial_node_status()
        self.task.width = 1000
        self.task.height = 1000
        self.task.all_texts = []
        click = patch.object(utils, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)

    def test_quotas_skip_bare_names_and_merge_duplicates(self):
        self.task.config["卡组所需中立卡牌"] = ["环绕之光*1", "环绕之光*2", "装备包", "梦之边境*0"]
        self.assertEqual(utils._neutral_card_quotas(self.task), {"环绕之光": 3})

    def test_record_counts_per_card_until_reached(self):
        self.assertFalse(utils._neutral_card_quota_reached(self.task, "环绕之光"))
        utils._record_neutral_card(self.task, "环绕之光", "环绕之光")
        self.assertEqual(self.task.node_status["neutral_card_counts"], {"环绕之光": 1})
        self.assertEqual(self.task.node_status["neutral_card_count"], 1)
        self.assertTrue(utils._neutral_card_quota_reached(self.task, "环绕之光"))
        self.assertFalse(utils._neutral_card_quota_reached(self.task, "梦之边境"))

    def test_unlisted_card_counts_total_only(self):
        utils._record_neutral_card(self.task, "装备包")
        self.assertEqual(self.task.node_status["neutral_card_counts"], {})
        self.assertEqual(self.task.node_status["neutral_card_count"], 1)
        self.assertFalse(utils._neutral_card_quota_reached(self.task, "装备包"))

    def _reward(self, cards):
        self.task.node_status["node_count"] = 3
        with patch.object(utils, "_get_region_text", return_value="卡牌奖励"), \
                patch.object(utils, "recognize_cards", return_value=cards), \
                patch.object(utils, "find_target_card", return_value=([], [])):
            return utils.handle_card_reward(self.task)

    def test_reward_skips_reached_card_and_picks_next_priority(self):
        self.task.node_status["neutral_card_counts"] = {"环绕之光": 1}
        self.assertTrue(self._reward([_card("环绕之光", 0.2), _card("梦之边境", 0.6)]))
        self.click.assert_called_once_with(self.task, 0.6, 0.4)

    def test_reward_still_picks_card_below_quota(self):
        self.assertTrue(self._reward([_card("梦之边境", 0.6), _card("环绕之光", 0.2)]))
        self.click.assert_called_once_with(self.task, 0.2, 0.4)

    def test_layer_reset_keeps_counts_and_round_reset_clears(self):
        self.task.node_status["neutral_card_counts"] = {"环绕之光": 1}
        utils.reset_layer_status(self.task)
        self.assertEqual(self.task.node_status["neutral_card_counts"], {"环绕之光": 1})
        utils.reset_mission_status(self.task)
        self.assertEqual(self.task.node_status["neutral_card_counts"], {})

    def test_chaos_metadata(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertEqual(mode.default_config["卡组所需中立卡牌"], [])
        self.assertIn("卡牌名*数量", mode.config_description["卡组所需中立卡牌"])


if __name__ == "__main__":
    unittest.main()
