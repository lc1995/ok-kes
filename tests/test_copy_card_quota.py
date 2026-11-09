"""卡厄思复制卡牌次数离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils
from ChaosMode import ChaosMode


def _card(name, x=0.4, y=0.4):
    return {"name": name, "x": x, "y": y}


def _box(name, x, y, width, height):
    box = SimpleNamespace(name=name, x=x, y=y, width=width, height=height)
    box.area = lambda: width * height
    return box


class TestCopyCardQuota(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.name = "自动卡厄思模式"
        self.task.config = {
            "游戏语言": "简体中文",
            "复制卡牌列表": ["卡牌A*2", "卡牌B*1"],
        }
        self.task.node_status = utils._initial_node_status()
        self.task.member_status = utils._initial_member_status()
        self.task.width = 1000
        self.task.height = 1000
        self.task.all_texts = []
        self.task.ocr.return_value = []
        click = patch.object(utils, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)
        white = patch.object(utils, "region_white_ratio", return_value=0)
        white.start()
        self.addCleanup(white.stop)

    def _skip_button(self):
        return _box("跳过", 700, 900, 100, 50)

    def _select(self, cards, count=1):
        texts = [self._skip_button()]
        self.task.all_texts = texts
        self.task.ocr.return_value = texts
        with patch.object(utils, "recognize_cards_in_deck", return_value=cards):
            return utils._select_chaos_copy_cards(self.task, count)

    def test_parse_count_and_bare_name(self):
        self.assertEqual(utils._parse_copy_card_entry("展开极光*2"), ("展开极光", 2))
        self.assertEqual(utils._parse_copy_card_entry("剑雨×1"), ("剑雨", 1))
        self.assertEqual(utils._parse_copy_card_entry("剑雨 x 2"), ("剑雨", 2))
        self.assertEqual(utils._parse_copy_card_entry("剑雨 2张"), ("剑雨", 2))
        self.assertEqual(utils._parse_copy_card_entry("一缕光芒*2"), ("一缕光芒", 2))
        self.assertEqual(utils._parse_copy_card_entry("剑雨"), ("剑雨", None))
        self.assertIsNone(utils._parse_copy_card_entry("剑雨*0"))
        self.assertIsNone(utils._parse_copy_card_entry("  "))
        self.assertEqual(
            utils._copy_card_quotas(self.task),
            [("卡牌A", 2), ("卡牌B", 1)],
        )

    def test_metadata_explains_ordered_counts(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertEqual(
            mode.default_config["复制卡牌列表"],
            ["展开极光*1", "剑雨*1", "缕光芒*1", "一缕光芒*1", "万众英雄*1"],
        )
        self.assertIn("当前画面没有这张卡时", mode.config_description["复制卡牌列表"])
        self.assertIn("不复制其他卡牌", mode.config_description["复制卡牌列表"])
        self.assertIn("只写卡牌名时无限复制", mode.config_description["复制卡牌列表"])

    def test_first_card_is_copied_before_later_cards(self):
        self.assertTrue(self._select([_card("卡牌B", 0.2), _card("卡牌A", 0.6)]))
        self.click.assert_called_once_with(self.task, 0.6, 0.4)
        self.assertEqual(self.task.node_status["pending_copy_names"], ["卡牌A"])
        self.task.click_box.assert_not_called()

    def test_same_card_can_fill_multiple_slots_until_its_count(self):
        cards = [_card("卡牌A", 0.2), _card("卡牌A", 0.6), _card("卡牌B", 0.8)]
        self.assertTrue(self._select(cards, count=2))
        self.assertEqual(self.task.node_status["pending_copy_names"], ["卡牌A", "卡牌A"])
        self.assertEqual(self.click.call_count, 2)
        self.task.click_box.assert_not_called()

    def test_bare_name_copies_without_limit_and_blocks_later_cards(self):
        self.task.config["复制卡牌列表"] = ["卡牌A", "卡牌B*1"]
        self.task.node_status["copied_card_counts"] = {"卡牌A": 5}
        cards = [_card("卡牌A", 0.2), _card("卡牌A", 0.5), _card("卡牌B", 0.8)]
        self.assertTrue(self._select(cards, count=2))
        self.assertEqual(self.task.node_status["pending_copy_names"], ["卡牌A", "卡牌A"])
        self.assertEqual(self.click.call_count, 2)
        self.task.click_box.assert_not_called()

    def test_bare_name_merges_with_counted_duplicate_as_unlimited(self):
        self.task.config["复制卡牌列表"] = ["卡牌A*2", "卡牌A"]
        self.assertEqual(utils._copy_card_quotas(self.task), [("卡牌A", None)])

    def test_reached_count_moves_to_next_card(self):
        self.task.node_status["copied_card_counts"] = {"卡牌A": 2}
        self.assertTrue(self._select([_card("卡牌A", 0.2), _card("卡牌B", 0.7)]))
        self.click.assert_called_once_with(self.task, 0.7, 0.4)
        self.assertEqual(self.task.node_status["pending_copy_names"], ["卡牌B"])

    def test_missing_current_card_copies_the_next_visible_card(self):
        self.assertTrue(self._select([_card("卡牌B", 0.7)]))
        self.click.assert_called_once_with(self.task, 0.7, 0.4)
        self.assertEqual(self.task.node_status["pending_copy_names"], ["卡牌B"])
        self.task.click_box.assert_not_called()

    def test_missing_every_listed_card_skips(self):
        self.assertTrue(self._select([_card("其他卡")]))
        self.click.assert_not_called()
        self.task.click_box.assert_called_once()
        self.assertEqual(self.task.node_status["pending_copy_names"], [])
        self.assertEqual(self.task.node_status["copied_card_counts"], {})

    def test_satisfied_counts_skip_even_when_cards_are_visible(self):
        self.task.node_status["copied_card_counts"] = {"卡牌A": 2, "卡牌B": 1}
        self.assertTrue(self._select([_card("卡牌A"), _card("卡牌B")]))
        self.click.assert_not_called()
        self.task.click_box.assert_called_once()
        self.assertEqual(
            self.task.node_status["copied_card_counts"],
            {"卡牌A": 2, "卡牌B": 1},
        )

    def test_does_not_use_next_card_to_fill_a_short_count(self):
        self.task.node_status["copied_card_counts"] = {"卡牌A": 1}
        self.assertTrue(self._select([_card("卡牌A"), _card("卡牌B")], count=2))
        self.click.assert_not_called()
        self.task.click_box.assert_called_once()
        self.assertEqual(self.task.node_status["pending_copy_names"], [])

    def test_copy_button_commits_pending_count(self):
        self.task.node_status["pending_copy_names"] = ["卡牌A"]
        self.task.all_texts = [_box("复制", 900, 890, 90, 50)]
        with patch.object(utils, "is_button_active", return_value=True):
            self.assertTrue(utils.handle_copy(self.task))
        self.assertEqual(self.task.node_status["copied_card_counts"]["卡牌A"], 1)
        self.assertEqual(self.task.node_status["pending_copy_names"], [])
        self.task.click_box.assert_called_once()

    def test_inactive_copy_button_discards_pending_selection(self):
        self.task.node_status["pending_copy_names"] = ["卡牌A"]
        self.task.all_texts = [
            _box("复制", 900, 890, 90, 50),
            self._skip_button(),
        ]
        with patch.object(utils, "is_button_active", return_value=False):
            self.assertTrue(utils._select_chaos_copy_cards(self.task, 1))
        self.assertEqual(self.task.node_status["pending_copy_names"], [])
        self.assertEqual(self.task.node_status["copied_card_counts"], {})
        self.task.click_box.assert_called_once()
        self.click.assert_not_called()

    def test_choice_page_follows_the_same_order(self):
        prompt = SimpleNamespace(name="请选择要复制的卡牌", x=400, y=100, width=200, height=40)
        self.task.all_texts = [self._skip_button()]
        with patch.object(utils, "find_box_at_point", return_value=prompt), patch.object(
            utils, "recognize_cards", return_value=[_card("卡牌B", 0.2), _card("卡牌A", 0.8)]
        ):
            self.assertTrue(utils.handle_copy_card_choice(self.task))
        self.click.assert_called_once_with(self.task, 0.8, 0.4)
        self.assertEqual(self.task.node_status["copied_card_counts"]["卡牌A"], 1)
        self.task.click_box.assert_not_called()

    def test_choice_page_copies_later_card_when_earlier_card_is_absent(self):
        prompt = SimpleNamespace(name="请选择要复制的卡牌", x=400, y=100, width=200, height=40)
        self.task.all_texts = [self._skip_button()]
        with patch.object(utils, "find_box_at_point", return_value=prompt), patch.object(
            utils, "recognize_cards", return_value=[_card("卡牌B", 0.7)]
        ):
            self.assertTrue(utils.handle_copy_card_choice(self.task))
        self.click.assert_called_once_with(self.task, 0.7, 0.4)
        self.assertEqual(self.task.node_status["copied_card_counts"]["卡牌B"], 1)
        self.task.click_box.assert_not_called()

    def test_choice_page_skips_when_no_listed_card_is_visible(self):
        prompt = SimpleNamespace(name="请选择要复制的卡牌", x=400, y=100, width=200, height=40)
        self.task.all_texts = [self._skip_button()]
        with patch.object(utils, "find_box_at_point", return_value=prompt), patch.object(
            utils, "recognize_cards", return_value=[_card("其他卡")]
        ):
            self.assertTrue(utils.handle_copy_card_choice(self.task))
        self.click.assert_not_called()
        self.task.click_box.assert_called_once()
        self.assertEqual(self.task.node_status["copied_card_counts"], {})

    def test_sortie_keeps_priority_without_counts(self):
        self.task.name = "自动出击模式"
        self.task.config["复制卡牌列表"] = ["卡牌B", "卡牌A"]
        self.task.node_status["copied_card_counts"] = {"卡牌B": 9}
        prompt = SimpleNamespace(name="请选择要复制的卡牌", x=400, y=100, width=200, height=40)
        with patch.object(utils, "find_box_at_point", return_value=prompt), patch.object(
            utils, "find_target_card", return_value=([], [])
        ), patch.object(
            utils, "recognize_cards", return_value=[_card("卡牌A", 0.2), _card("卡牌B", 0.8)]
        ):
            self.assertTrue(utils.handle_copy_card_choice(self.task))
        self.click.assert_called_once_with(self.task, 0.8, 0.4)
        self.assertEqual(self.task.node_status["copied_card_counts"], {"卡牌B": 9})

    def test_counts_persist_across_layers_and_reset_each_run(self):
        self.task.node_status["copied_card_counts"] = {"卡牌A": 2}
        self.task.node_status["pass_final_boss_count"] = 1
        utils.reset_layer_status(self.task)
        self.assertEqual(self.task.node_status["copied_card_counts"], {"卡牌A": 2})
        self.assertEqual(self.task.node_status["pass_final_boss_count"], 1)
        utils.reset_mission_status(self.task)
        self.assertEqual(self.task.node_status["copied_card_counts"], {})


if __name__ == "__main__":
    unittest.main()
