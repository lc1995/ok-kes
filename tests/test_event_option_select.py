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

    def _assert_clicked(self, x, y):
        self.click.assert_called_once()
        args = self.click.call_args.args
        self.assertIs(args[0], self.task)
        self.assertAlmostEqual(args[1], x)
        self.assertAlmostEqual(args[2], y)
