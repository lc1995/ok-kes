"""德朗商店：后台进店需先移动鼠标且不能无限重试；程序在商店内重启也要能移除卡牌。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils


def _text(name, cx, cy, width=1600, height=900):
    box = Mock(x=cx * width - 40, y=cy * height - 12, width=80, height=24)
    box.name = name
    box.area.return_value = 80 * 24
    return box


class TestShopEntry(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.width = 1600
        self.task.height = 900
        self.task.config = {}
        self.task.default_config = {}
        self.task.node_status = {"shop": True, "flash_or_rest": False}
        self.task.all_texts = [_text("德朗商店", 0.360, 0.138)]
        self.task.find_one.return_value = None
        for name, value in (
            ("_click_special_flash", False),
            ("_find_rest_feature", None),
            ("_get_region_text", ""),
            ("_member_deck_state", {}),
            ("_get_current_credit", 0),
        ):
            p = patch.object(utils, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        click = patch.object(utils, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)

    def test_entry_moves_mouse_then_gives_up_after_five_tries(self):
        for _ in range(utils.SHOP_ENTER_MAX_ATTEMPTS):
            self.assertTrue(utils.handle_rest(self.task))
        self.task.click_box.assert_not_called()
        self.assertEqual(self.click.call_count, utils.SHOP_ENTER_MAX_ATTEMPTS)
        x, y = self.click.call_args.args[1:]
        self.assertAlmostEqual(x, 0.360)
        self.assertAlmostEqual(y, 0.138)

        self.assertFalse(utils.handle_rest(self.task))
        self.assertFalse(self.task.node_status["shop"])
        self.assertEqual(self.click.call_count, utils.SHOP_ENTER_MAX_ATTEMPTS)


class TestShopRemove(unittest.TestCase):
    def test_remove_card_after_restart_inside_shop(self):
        task = Mock()
        task.width = 1600
        task.height = 900
        task.node_status = {"shop": False}
        remove = _text("移除卡牌", 0.729, 0.261)
        task.all_texts = [remove, _text("80", 0.724, 0.319)]
        with patch.object(utils, "_get_current_credit", return_value=1014):
            self.assertTrue(utils.handle_shop(task))
        task.click_box.assert_called_once_with(remove)
        self.assertTrue(task.node_status["shop_remove_clicked"])


if __name__ == "__main__":
    unittest.main()
