"""章鱼接管的离线行为验证，不连接游戏、不发送键鼠输入。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils_chaos
from ChaosMode import ChaosMode


class TestOctopusHandoff(unittest.TestCase):
    def test_task_initializes_with_protection_enabled(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertTrue(mode.default_config["遇到章鱼暂停"])
        self.assertFalse(mode._octopus_handoff)

    def test_stop_then_controller_start_does_not_reuse_previous_handoff(self):
        from ok.gui.StartController import StartController

        mode = ChaosMode(executor=Mock(), app=Mock())
        mode.config = {"遇到章鱼暂停": True, "_enabled": True}
        mode._enabled = True
        mode._octopus_handoff = True
        mode.disable()
        self.assertFalse(mode.enabled)
        self.assertFalse(mode.config["_enabled"])
        # 任务卡的开始入口直接标记启用，不调用 ChaosMode.enable()。
        StartController._mark_task_enabled(mode)
        self.assertTrue(mode.enabled)
        with patch.object(utils_chaos, "match_octopus", return_value=None):
            self.assertFalse(utils_chaos.handle_octopus_handoff(mode))
        mode.executor.pause.assert_not_called()

    def setUp(self):
        self.task = Mock()
        self.task.config = {"遇到章鱼暂停": True}
        self.task._octopus_handoff = False
        self.task._octopus_scan_log_time = 0
        detector = patch.object(utils_chaos, "match_octopus")
        self.detector = detector.start()
        self.addCleanup(detector.stop)
        self.detector.return_value = SimpleNamespace(confidence=0.94, x=100, y=100, width=50, height=70)
        self.task.node_status = {"node_count": 12, "pass_final_boss_count": 1}
        self.task.next_frame.return_value = object()

    def handle(self, states):
        with patch.object(utils_chaos, "_octopus_auto_battle_state", side_effect=states), \
                patch.object(utils_chaos, "_move_and_click") as click, \
                patch.object(utils_chaos, "_simplify_texts", return_value=[]):
            result = utils_chaos.handle_octopus_handoff(self.task)
        return result, click

    def test_no_enemy_leaves_normal_flow_alone(self):
        self.detector.return_value = None
        self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.task.executor.pause.assert_not_called()

    def test_below_threshold_does_not_pause(self):
        self.detector.return_value.confidence = 0.749
        self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.task.executor.pause.assert_not_called()

    def test_threshold_hit_uses_new_detector_and_records_location(self):
        self.detector.return_value.confidence = 0.75
        result, _ = self.handle([False])
        self.assertTrue(result)
        self.task.find_one.assert_not_called()
        self.assertTrue(any('位置=' in call.args[0] and call.kwargs.get('screenshot')
                            for call in self.task.log_info.call_args_list))

    def test_disabled_option_does_not_scan_or_pause(self):
        self.task.config["遇到章鱼暂停"] = False
        self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.detector.assert_not_called()

    def test_already_off_pauses_without_toggling_or_resetting_progress(self):
        result, click = self.handle([False])
        self.assertTrue(result)
        click.assert_not_called()
        self.task.executor.pause.assert_called_once()
        self.assertTrue(self.task._octopus_handoff)
        self.assertEqual(self.task.node_status, {"node_count": 12, "pass_final_boss_count": 1})

    def test_enabled_auto_is_clicked_once_and_checked_on_new_frame(self):
        result, click = self.handle([True, False])
        self.assertTrue(result)
        click.assert_called_once_with(self.task, 0.880, 0.056)
        self.task.next_frame.assert_called_once()
        self.task.executor.pause.assert_called_once()
        self.assertIn("已关闭", self.task.log_warning.call_args.args[0])

    def test_failed_close_does_not_retry_toggle(self):
        _, click = self.handle([True, True])
        click.assert_called_once()
        self.assertIn("无法确认", self.task.log_warning.call_args.args[0])
        self.task.executor.pause.assert_called_once()

    def test_transition_with_unknown_auto_state_still_pauses(self):
        _, click = self.handle([None])
        click.assert_not_called()
        self.assertIn("手动检查", self.task.log_warning.call_args.args[0])
        self.task.executor.pause.assert_called_once()

    def test_missing_frame_after_click_reports_unknown(self):
        self.task.next_frame.return_value = None
        self.handle([True])
        self.assertIn("无法确认", self.task.log_warning.call_args.args[0])
        self.task.executor.pause.assert_called_once()

    def test_resume_during_battle_repauses_even_if_enemy_template_disappears(self):
        self.task._octopus_handoff = True
        self.detector.return_value = None
        with patch.object(utils_chaos, "_octopus_handoff_finished", return_value=False):
            result, _ = self.handle([False])
        self.assertTrue(result)
        self.task.executor.pause.assert_called_once()

    def test_resume_on_reward_preserves_progress_and_resets_stuck_timer(self):
        self.task._octopus_handoff = True
        self.detector.return_value = None
        with patch.object(utils_chaos, "_octopus_handoff_finished", return_value=True):
            self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.assertFalse(self.task._octopus_handoff)
        self.assertIsNone(self.task._prev_frame_gray)
        self.assertIsInstance(self.task._last_change_time, float)
        self.assertEqual(self.task.node_status["node_count"], 12)
        self.task.executor.pause.assert_not_called()

    def test_notification_failure_still_pauses(self):
        self.task.log_warning.side_effect = RuntimeError("notification failed")
        with self.assertRaises(RuntimeError):
            self.handle([False])
        self.task.executor.pause.assert_called_once()

    def test_run_never_calls_page_handlers_after_handoff(self):
        handler = Mock()
        with patch.object(utils_chaos, "handle_octopus_handoff", return_value=True), \
                patch.object(utils_chaos, "PAGE_HANDLERS", [handler]), \
                patch("ChaosMode._simplify_texts", return_value=[]):
            ChaosMode.run(self.task)
        handler.assert_not_called()
        self.task._check_upload_if_needed.assert_not_called()

    def test_reward_title_does_not_unlock_while_hand_counter_is_present(self):
        with patch.object(utils_chaos, "find_box_at_point", return_value=SimpleNamespace(name="3/10")):
            self.assertFalse(utils_chaos._octopus_handoff_finished(self.task))

    def test_equipment_reward_is_a_resume_point(self):
        with patch.object(utils_chaos, "find_box_at_point", return_value=None), \
                patch.object(utils_chaos, "_get_region_text", return_value="装备"):
            self.assertTrue(utils_chaos._octopus_handoff_finished(self.task))

    def set_team_selection_texts(self, include_enter=True):
        self.task.width, self.task.height = 1920, 1080
        self.task.all_texts = [
            SimpleNamespace(name="配置队伍", x=150, y=35, width=180, height=40),
        ]
        if include_enter:
            self.task.all_texts.append(
                SimpleNamespace(name="进入", x=1770, y=970, width=80, height=40))

    def test_team_selection_clears_pending_handoff_without_resetting_progress(self):
        self.set_team_selection_texts()
        self.task._octopus_handoff = True
        self.detector.return_value = None
        with patch.object(utils_chaos, "find_box_at_point", return_value=None):
            self.assertFalse(utils_chaos.handle_octopus_handoff(self.task))
        self.assertFalse(self.task._octopus_handoff)
        self.assertEqual(self.task.node_status["node_count"], 12)
        self.task.executor.pause.assert_not_called()

    def test_team_selection_title_alone_does_not_clear_handoff(self):
        self.set_team_selection_texts(include_enter=False)
        self.task.find_one.return_value = None
        with patch.object(utils_chaos, "find_box_at_point", return_value=None):
            self.assertFalse(utils_chaos._octopus_handoff_finished(self.task))

    def test_team_selection_does_not_override_visible_battle_counter(self):
        self.set_team_selection_texts()
        with patch.object(utils_chaos, "find_box_at_point", return_value=SimpleNamespace(name="3/10")):
            self.assertFalse(utils_chaos._octopus_handoff_finished(self.task))

    def test_auto_state_is_unknown_without_visible_auto_control(self):
        with patch.object(utils_chaos, "find_box_at_point", return_value=SimpleNamespace(name="3/10")), \
                patch.object(utils_chaos, "_get_region_text", return_value=""):
            self.assertIsNone(utils_chaos._octopus_auto_battle_state(self.task))

    def test_auto_indicator_with_visible_battle_controls(self):
        self.task.width, self.task.height = 1920, 1080
        self.task.frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        x, y = int(0.877 * 1920), int(0.050 * 1080)
        with patch.object(utils_chaos, "find_box_at_point", return_value=SimpleNamespace(name="3/10")), \
                patch.object(utils_chaos, "_get_region_text", return_value="AUTO"):
            self.task.frame[y:y + 4, x:x + 4] = (255, 255, 255)
            self.assertFalse(utils_chaos._octopus_auto_battle_state(self.task))
            self.task.frame[y:y + 4, x:x + 4] = (50, 120, 200)
            self.assertTrue(utils_chaos._octopus_auto_battle_state(self.task))


if __name__ == "__main__":
    unittest.main()
