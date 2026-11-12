"""事件选项选择离线验证，不连接游戏。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils


def _option(description, x, y, region):
    return {
        "x": x,
        "y": y,
        "description": description,
        "description_region": region,
        "feature_name": "event4",
        "confidence": 0.99,
    }


REVELATION = _option(
    "精密加工记忆领受计划的启示",
    0.35,
    0.969,
    (0.25, 0.70, 0.48, 0.88),
)
LEAVE = _option(
    "就此离开事件结束",
    0.63,
    0.908,
    (0.51, 0.70, 0.75, 0.89),
)
PICKUP = _option(
    "01000010捡起01011001触发事件生命值恢复所有主战员压力减少9",
    0.35,
    0.969,
    (0.25, 0.70, 0.48, 0.88),
)


class TestEventOptionSelect(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.name = "自动卡厄思模式"
        self.task.width = 1920
        self.task.height = 1080
        self.task.all_texts = []
        self.task.node_status = {}
        self.task.find_feature.return_value = []
        self.task.find_one.return_value = None
        recognize = patch.object(
            utils,
            "recognize_event_options",
            return_value=[REVELATION, LEAVE],
        )
        click = patch.object(utils, "_move_and_click")
        self.recognize = recognize.start()
        self.click = click.start()
        self.addCleanup(recognize.stop)
        self.addCleanup(click.stop)

    def test_revelation_is_clicked_before_higher_leave_icon(self):
        self.assertTrue(utils.handle_event_task(self.task))

        self.click.assert_called_once_with(self.task, 0.365, 0.79)
        logs = "\n".join(call.args[0] for call in self.task.log_info.call_args_list)
        self.assertIn("检测到「领受计划的启示」", logs)
        self.assertNotIn("Y坐标小于0.925", logs)

    def test_visited_precision_memory_still_leaves(self):
        self.task.node_status["precision_memory_visited"] = True

        self.assertTrue(utils.handle_event_task(self.task))

        self._assert_clicked(0.63, 0.795)
        self.assertFalse(self.task.node_status["precision_memory_visited"])

    def test_higher_icon_is_still_selected_without_revelation(self):
        other = _option("其他事件", 0.35, 0.969, (0.25, 0.70, 0.48, 0.88))
        self.recognize.return_value = [other, LEAVE]

        self.assertTrue(utils.handle_event_task(self.task))

        self._assert_clicked(0.63, 0.795)
        logs = "\n".join(call.args[0] for call in self.task.log_info.call_args_list)
        self.assertIn("Y坐标小于0.925", logs)

    def test_special_flash_is_clicked_before_event_option(self):
        flash = Mock(x=900, y=400, width=70, height=68, confidence=0.93)
        flash.name = "special_flash"

        def find_one(feature_name=None, **_kwargs):
            names = feature_name if isinstance(feature_name, (list, tuple)) else [feature_name]
            if any(
                name in ("special_flash", "special_flash_luosi", "special_flash_luosi2")
                for name in names
            ):
                return flash
            return None

        self.task.find_one.side_effect = find_one
        self.assertTrue(utils.handle_event_task(self.task))
        self.task.click_box.assert_called_once_with(flash)
        self.click.assert_not_called()
        logs = "\n".join(call.args[0] for call in self.task.log_info.call_args_list)
        self.assertIn("先点击触发神闪", logs)

    def test_binary_pickup_event_is_clicked_before_higher_leave_icon(self):
        self.task.config = {"拉黑任务": ["咒术卡牌", "压力"]}
        self.recognize.return_value = [PICKUP, LEAVE]

        self.assertTrue(utils.handle_event_task(self.task))

        self.click.assert_called_once_with(self.task, 0.365, 0.79)
        logs = "\n".join(call.args[0] for call in self.task.log_info.call_args_list)
        self.assertIn("检测到「01000」事件", logs)
        self.assertNotIn("Y坐标小于0.925", logs)

    def _text(self, name, cx, cy):
        box = Mock(x=cx * 1920 - 100, y=cy * 1080 - 15, width=200, height=30)
        box.name = name
        return box

    def test_binary_pickup_card_is_clicked_by_ocr_without_event_icon(self):
        title = self._text("01000010捡起01011001", 0.730, 0.736)
        self.task.all_texts = [title, self._text("少9，移除1张所选卡牌", 0.731, 0.900)]
        self.recognize.return_value = []

        self.assertTrue(utils.handle_event_task(self.task))

        self.task.click_box.assert_called_once_with(title)
        logs = "\n".join(call.args[0] for call in self.task.log_info.call_args_list)
        self.assertIn("检测到「01000」事件卡", logs)

    def test_three_choice_remove_ignores_event_card_description(self):
        self.task.all_texts = [self._text("少9，移除1张所选卡牌", 0.731, 0.900)]

        self.assertFalse(utils.handle_three_choice_card_remove(self.task))
        self.task.click_box.assert_not_called()

    def _assert_clicked(self, x, y):
        self.click.assert_called_once()
        args = self.click.call_args.args
        self.assertIs(args[0], self.task)
        self.assertAlmostEqual(args[1], x)
        self.assertAlmostEqual(args[2], y)
