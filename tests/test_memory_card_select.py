"""记忆卡牌选择页重新搜索的离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils_chaos


def _box(name, rel_x, rel_y, width=80, height=30, screen=1000):
    return SimpleNamespace(
        name=name,
        x=rel_x * screen - width / 2,
        y=rel_y * screen - height / 2,
        width=width,
        height=height,
    )


def _card(name, feature_x, feature_y, click_x=None, click_y=None):
    return {
        "name": name,
        "description": "",
        "x": feature_x if click_x is None else click_x,
        "y": 0.24 if click_y is None else click_y,
        "feature_box": _box("", feature_x, feature_y, width=20, height=20),
    }


class TestMemoryCardSelect(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.width = 1000
        self.task.height = 1000
        self.task.config = {
            "游戏语言": "简体中文",
            "指定记忆卡牌": "记忆：丧失",
        }
        self.task.all_texts = [
            _box("选择铭刻的记忆", 0.50, 0.09, width=180, height=40),
        ]

        def _region_ocr(x=0, y=0, to_x=1, to_y=1, **kwargs):
            found = []
            for box in self.task.all_texts:
                center_x = (box.x + box.width / 2) / self.task.width
                center_y = (box.y + box.height / 2) / self.task.height
                if x <= center_x <= to_x and y <= center_y <= to_y:
                    found.append(box)
            return found

        self.task.ocr.side_effect = _region_ocr
        recognize = patch.object(utils_chaos, "recognize_cards", return_value=[])
        target = patch.object(utils_chaos, "find_target_card", return_value=([], []))
        click = patch.object(utils_chaos, "_move_and_click")
        self.recognize = recognize.start()
        self.target = target.start()
        self.click = click.start()
        self.addCleanup(recognize.stop)
        self.addCleanup(target.stop)
        self.addCleanup(click.stop)

    def _cards(self):
        return [
            _card("记忆：贪婪", 0.2135, 0.2833, 0.22, 0.24),
            _card("记忆：王国", 0.4573, 0.2833, 0.46, 0.24),
            _card("记忆：女子", 0.6937, 0.2833, 0.70, 0.24),
            _card("击卡牌，则自身攻击力", 0.4234, 0.6806, 0.42, 0.64),
        ]

    def _logs(self):
        return "\n".join(call.args[0] for call in self.task.log_info.call_args_list)

    def test_button_below_description_is_clicked(self):
        self.recognize.return_value = self._cards()
        self.task.all_texts.extend([
            _box("重新搜索", 0.20, 0.84),
            _box("2/3次", 0.30, 0.84),
        ])

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        self.click.assert_called_once()
        _, click_x, click_y = self.click.call_args.args
        self.assertAlmostEqual(click_x, 0.20, places=3)
        self.assertAlmostEqual(click_y, 0.84, places=3)
        self.assertIn("剩余搜索次数=2，点击重新搜索", self._logs())

    def test_merged_label_and_count_is_clicked(self):
        self.recognize.return_value = [_card("记忆：王国", 0.4573, 0.2833, 0.46, 0.24)]
        self.task.all_texts.append(_box("重新搜索 2/3", 0.46, 0.84, width=140))

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        _, click_x, click_y = self.click.call_args.args
        self.assertAlmostEqual(click_x, 0.46, places=3)
        self.assertAlmostEqual(click_y, 0.84, places=3)

    def test_split_label_is_clicked(self):
        self.recognize.return_value = [_card("记忆：王国", 0.4573, 0.2833, 0.46, 0.24)]
        self.task.all_texts.extend([
            _box("重新", 0.42, 0.84, width=40),
            _box("搜索", 0.50, 0.84, width=40),
            _box("1/3", 0.56, 0.84, width=40),
        ])

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        _, click_x, click_y = self.click.call_args.args
        self.assertAlmostEqual(click_x, 0.46, places=3)
        self.assertAlmostEqual(click_y, 0.84, places=3)

    def test_zero_count_skips_false_card(self):
        self.recognize.return_value = self._cards()
        self.task.all_texts.extend([
            _box("重新搜索", 0.20, 0.84),
            _box("0 / 3", 0.30, 0.84),
        ])
        chosen = []

        def _choice(items):
            chosen.append(list(items))
            return items[0]

        with patch.object(utils_chaos.random, "choice", side_effect=_choice):
            self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        self.assertIn("剩余搜索次数=0，跳过重新搜索", self._logs())
        self.assertIn("重新搜索次数已用完", self._logs())
        self.assertEqual([card["name"] for card in chosen[0]], ["记忆：贪婪", "记忆：王国", "记忆：女子"])
        self.click.assert_called_once_with(self.task, 0.22, 0.24)

    def test_traditional_refresh_label_is_clicked(self):
        self.task.config["游戏语言"] = "繁体中文"
        self.recognize.return_value = [_card("记忆：王国", 0.4573, 0.2833, 0.46, 0.24)]
        self.task.all_texts.append(_box("重新探索1/3", 0.46, 0.84, width=140))

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        _, click_x, click_y = self.click.call_args.args
        self.assertAlmostEqual(click_x, 0.46, places=3)
        self.assertAlmostEqual(click_y, 0.84, places=3)

    def test_columns_follow_memory_prefix_not_fixed_names(self):
        self.recognize.return_value = [
            _card("记忆：甲", 0.2135, 0.2833, 0.22, 0.24),
            _card("普通强化", 0.4573, 0.2833, 0.46, 0.24),
            _card("记忆： 乙", 0.6937, 0.2833, 0.70, 0.24),
            _card("击卡牌，则自身攻击力", 0.4234, 0.6806, 0.42, 0.64),
        ]
        self.task.all_texts.extend([
            _box("重新搜索", 0.20, 0.84),
            _box("0/3", 0.30, 0.84),
            _box("重新搜索", 0.70, 0.84),
            _box("0/3", 0.78, 0.84),
        ])
        chosen = []

        def _choice(items):
            chosen.append([card["name"] for card in items])
            return items[0]

        with patch.object(utils_chaos.random, "choice", side_effect=_choice):
            self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        self.assertEqual(chosen, [["记忆：甲", "记忆： 乙"]])
        self.click.assert_called_once_with(self.task, 0.22, 0.24)

    def test_specified_memory_is_chosen_before_refresh(self):
        cards = self._cards()
        cards[0]["name"] = "记忆：丧失"
        self.recognize.return_value = cards
        self.task.all_texts.append(_box("重新搜索 2/3", 0.46, 0.84, width=140))

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        self.click.assert_called_once_with(self.task, 0.22, 0.24)
        self.assertIn("命中指定记忆卡牌「记忆：丧失」", self._logs())

    def test_button_below_old_band_is_clicked(self):
        self.recognize.return_value = self._cards()
        self.task.all_texts.extend([
            _box("重新搜索", 0.20, 0.96),
            _box("2/3", 0.30, 0.96),
            _box("长按卡牌以查看信息。", 0.50, 0.93, width=180),
        ])

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        _, click_x, click_y = self.click.call_args.args
        self.assertAlmostEqual(click_x, 0.20, places=3)
        self.assertAlmostEqual(click_y, 0.96, places=3)
        self.assertIn("剩余搜索次数=2，点击重新搜索", self._logs())

    def test_button_outside_card_columns_is_clicked(self):
        self.recognize.return_value = self._cards()
        self.task.all_texts.append(_box("重新搜索 1/3", 0.95, 0.50, width=140))

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        _, click_x, click_y = self.click.call_args.args
        self.assertAlmostEqual(click_x, 0.95, places=3)
        self.assertAlmostEqual(click_y, 0.50, places=3)

    def test_other_row_fraction_does_not_override_button_count(self):
        self.recognize.return_value = self._cards()
        self.task.all_texts.extend([
            _box("1/2", 0.25, 0.64),
            _box("重新搜索", 0.20, 0.96),
            _box("2/3", 0.30, 0.96),
        ])

        self.assertTrue(utils_chaos.handle_memory_card_select(self.task))

        self.assertIn("剩余搜索次数=2，点击重新搜索", self._logs())
