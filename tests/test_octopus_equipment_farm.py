"""刷指定章鱼装备的离线验证，不连接游戏、不发送键鼠输入。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils_chaos
from ChaosMode import ChaosMode


class TextBox:
    def __init__(self, name, x, y, width=40, height=20):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height


class TestOctopusEquipmentFarm(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.width = self.task.height = 1000
        self.task.config = {"刷章鱼装备": "混沌之识", "游戏语言": "简体中文"}
        self.task.node_status = {
            "octopus_seen": True,
            "octopus_drop_checked": False,
            "octopus_drop_rejected": False,
            "octopus_drop_matched": False,
            "octopus_seen_names": [],
        }
        self.task.find_feature.return_value = []
        self.task.all_texts = []
        click = patch.object(utils_chaos, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)

    def add_text(self, name, rel_x, rel_y):
        self.task.all_texts.append(TextBox(name, rel_x * 1000 - 20, rel_y * 1000 - 10))

    def show_equipment_page(self, names):
        self.task.all_texts = []
        self.add_text("装备", 0.499, 0.126)
        regions = ((0.50, 0.25), (0.50, 0.58))
        for name, (x, y) in zip(names, regions):
            self.add_text(name, x, y)
            self.add_text("武器", x - 0.05, y + 0.04)

    def show_install_page(self, name):
        self.task.all_texts = []
        self.add_text("装备", 0.499, 0.126)
        self.add_text("请选择主战员", 0.921, 0.135)
        self.add_text(name, 0.34, 0.40)

    def show_route(self):
        self.task.all_texts = []
        self.task.find_feature.return_value = [TextBox("position", 400, 600)]

    def test_config_defaults_to_disabled(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertEqual(mode.default_config["刷章鱼装备"], "")
        self.assertIn("一件都没对上", mode.config_description["刷章鱼装备"])
        self.assertFalse(mode.node_status["octopus_seen"])
        self.assertFalse(mode.node_status["octopus_drop_matched"])

    def test_unmatched_equipment_does_not_restart_before_the_route(self):
        self.show_equipment_page(["乱世之触"])
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.show_install_page("怪异之壳")
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()
        self.assertFalse(self.task.node_status["octopus_drop_matched"])
        self.assertEqual(self.task.node_status["octopus_seen_names"], ["乱世之触", "怪异之壳"])

    def test_any_match_in_the_stage_is_kept_until_the_route(self):
        self.show_equipment_page(["乱世之触"])
        utils_chaos.handle_octopus_equipment_drop(self.task)
        self.show_equipment_page(["混沌之识", "拷问工具箱"])
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()
        self.assertTrue(self.task.node_status["octopus_drop_matched"])
        self.assertFalse(self.task.node_status["octopus_drop_checked"])

    def test_route_restarts_when_nothing_in_the_stage_matched(self):
        self.show_equipment_page(["乱世之触"])
        utils_chaos.handle_octopus_equipment_drop(self.task)
        self.show_install_page("怪异之壳")
        utils_chaos.handle_octopus_equipment_drop(self.task)
        self.show_route()
        self.assertTrue(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_called_once_with(self.task, 0.959, 0.053)
        self.assertTrue(self.task.node_status["octopus_drop_rejected"])

    def test_route_continues_when_any_equipment_matched(self):
        self.task.config["刷章鱼装备"] = "混沌"
        self.show_equipment_page(["关卡武器"])
        utils_chaos.handle_octopus_equipment_drop(self.task)
        self.show_install_page("混沌之识")
        utils_chaos.handle_octopus_equipment_drop(self.task)
        self.show_route()
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()
        self.assertTrue(self.task.node_status["octopus_drop_checked"])
        self.assertFalse(self.task.node_status["octopus_drop_rejected"])

    def test_incomplete_equipment_page_does_not_restart(self):
        self.add_text("装备", 0.499, 0.126)
        self.add_text("武器", 0.45, 0.29)
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()
        self.assertFalse(self.task.node_status["octopus_drop_checked"])

    def test_unseen_octopus_does_not_restart_on_route(self):
        self.task.node_status["octopus_seen"] = False
        self.show_route()
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()

    def test_battle_screen_does_not_count_as_stage_end(self):
        self.show_equipment_page(["乱世之触"])
        utils_chaos.handle_octopus_equipment_drop(self.task)
        self.task.all_texts = []
        self.task.find_feature.return_value = [TextBox("position", 400, 600)]
        self.add_text("3/10", 0.512, 0.969)
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()

    def test_rejected_drop_lets_confirm_dialog_through(self):
        self.task.node_status["octopus_drop_rejected"] = True
        self.add_text("装备", 0.499, 0.126)
        self.add_text("确认", 0.50, 0.50)
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()

    def test_rejected_drop_blocks_equipment_page_until_it_closes(self):
        self.task.node_status["octopus_drop_rejected"] = True
        self.add_text("装备", 0.499, 0.126)
        self.assertTrue(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()

    def test_detection_marks_octopus_without_pausing_when_farming(self):
        self.task.config["遇到章鱼暂停"] = False
        self.task.node_status["octopus_seen"] = False
        self.task._octopus_scan_log_time = 0
        enemy = SimpleNamespace(confidence=0.9, x=1, y=2, width=3, height=4)
        with patch.object(utils_chaos, "match_octopus", return_value=enemy):
            self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.assertTrue(self.task.node_status["octopus_seen"])
        self.task.executor.pause.assert_not_called()

    def test_empty_farm_config_ignores_pause_target(self):
        self.task.config["刷章鱼装备"] = ""
        self.task.config["得到指定装备后暂停"] = "乱世之触"
        self.assertEqual(utils_chaos._octopus_equipment_target(self.task), "")
        self.show_install_page("怪异之壳")
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.show_route()
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_not_called()

    def test_ocr_name_marks_seen_without_eye_match(self):
        self.task.config["遇到章鱼暂停"] = False
        self.task.node_status["octopus_seen"] = False
        self.task._octopus_scan_log_time = 0
        self.add_text("无限之触手+2", 0.50, 0.08)
        with patch.object(utils_chaos, "match_octopus", return_value=None):
            self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.assertTrue(self.task.node_status["octopus_seen"])

    def test_octopus_drop_name_marks_seen_then_route_restarts(self):
        self.task.node_status["octopus_seen"] = False
        self.task.config["刷章鱼装备"] = "乱世之触"
        self.show_install_page("怪异之壳")
        self.assertFalse(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.assertTrue(self.task.node_status["octopus_seen"])
        self.show_route()
        self.assertTrue(utils_chaos.handle_octopus_equipment_drop(self.task))
        self.click.assert_called_once_with(self.task, 0.959, 0.053)

    def test_all_six_octopus_drops_are_recognized(self):
        for name in ("乱世之触", "怪异之壳", "混沌之识", "灾难之像", "随机之球", "错乱之骰"):
            self.assertTrue(utils_chaos._is_octopus_drop_name(name), name)
        self.assertFalse(utils_chaos._is_octopus_drop_name("拷问工具箱"))
