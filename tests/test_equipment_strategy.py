"""装备策略离线验证，不连接游戏、不发送键鼠输入。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils
from ChaosMode import ChaosMode


def box(name, x=800, y=930):
    return SimpleNamespace(name=name, x=x, y=y, width=20, height=20)


class TestEquipmentStrategy(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.width = self.task.height = 1000
        self.task.default_config = {"刷存档主战员": "海德玛丽"}
        self.task.config = {
            "装备选择策略": "仅目标主战员列表装备",
            "装备1号位优先级": ["目标武器", "备用武器"],
            "装备2号位优先级": ["目标防具"],
            "装备3号位优先级": [],
        }
        self.task.member_status = utils._initial_member_status()
        self.task.node_status = {}
        self.refine = box("提炼")
        self.task.all_texts = [self.refine, box("确认", x=920)]
        self.levels = [box("等级", y=300), box("等级", y=500), box("等级", y=700)]
        self.target_index = 1
        self.qualities = ["", "", ""]
        click = patch.object(utils, "_move_and_click")
        self.click = click.start()
        self.addCleanup(click.stop)

    def equipment(self, name="目标武器", slot=0, quality="普通"):
        priority = self.task.config[f"装备{slot + 1}号位优先级"]
        canonical, rank = utils._match_equipment_name(name, priority)
        return dict(name=canonical or name, ocr_name=name, slot=slot, quality=quality,
                    description="描述", priority=priority, rank=rank)

    def install(self, item):
        with patch.object(utils, "find_box_at_point", side_effect=[box("装备"), box("请选择主战员")]), \
                patch.object(utils, "_equipment_info", return_value=item), \
                patch.object(utils, "_find_member_level_tags", return_value=self.levels), \
                patch.object(utils, "_find_target_member_index", return_value=self.target_index), \
                patch.object(utils, "_member_equipment_qualities", return_value=self.qualities), \
                patch.object(utils, "_get_current_credit", return_value=500):
            return utils.handle_equipment(self.task)

    def select(self, items):
        with patch.object(utils, "find_box_at_point", side_effect=[box("装备"), None]), \
                patch.object(utils, "_equipment_info", side_effect=items):
            return utils.handle_equipment(self.task)

    def assert_refined(self):
        self.task.click_box.assert_called_once_with(self.refine)
        self.click.assert_not_called()

    def test_metadata_is_single_choice_and_defaults_to_original(self):
        mode = ChaosMode(executor=Mock(), app=Mock())
        self.assertEqual(mode.default_config["装备选择策略"], "原有策略")
        self.assertEqual(mode.config_type["装备选择策略"], {
            "type": "drop_down", "options": ["原有策略", "仅目标主战员列表装备"],
        })

    def test_strict_unlisted_equipment_is_refined_even_with_empty_slots_and_teammates(self):
        self.assertTrue(self.install(self.equipment("未配置装备", quality="传说")))
        self.assert_refined()
        self.assertEqual(self.task.member_status["equipment"]["names"], ["", "", ""])

    def test_strict_listed_equipment_goes_to_target_and_updates_state(self):
        self.install(self.equipment())
        self.click.assert_called_once_with(self.task, 0.756, 0.510)
        self.task.click_box.assert_not_called()
        self.assertEqual(self.task.member_status["equipment"]["names"][0], "目标武器")

    def test_strict_does_not_downgrade_or_give_duplicate_to_teammates(self):
        self.task.member_status["equipment"]["names"][0] = "目标武器"
        self.qualities[0] = "史诗"
        self.install(self.equipment("备用武器", quality="传说"))
        self.assert_refined()

    def test_strict_same_name_better_quality_upgrades(self):
        self.task.member_status["equipment"]["names"][0] = "目标武器"
        self.qualities[0] = "普通"
        self.install(self.equipment(quality="史诗"))
        self.click.assert_called_once_with(self.task, 0.756, 0.510)
        self.task.click_box.assert_not_called()

    def test_strict_respects_legendary_limit(self):
        self.qualities[1] = "传说"
        self.install(self.equipment(quality="传说"))
        self.assert_refined()

    def test_strict_missing_target_does_not_fall_back_to_teammates(self):
        self.target_index = None
        self.install(self.equipment())
        self.assert_refined()

    def test_old_config_still_installs_unlisted_equipment_in_empty_target_slot(self):
        self.task.config.pop("装备选择策略")
        self.install(self.equipment("未配置装备"))
        self.click.assert_called_once_with(self.task, 0.756, 0.510)
        self.task.click_box.assert_not_called()

    def test_original_strategy_still_gives_unneeded_equipment_to_teammates(self):
        self.task.config["装备选择策略"] = "原有策略"
        self.task.member_status["equipment"]["names"][0] = "目标武器"
        self.qualities[0] = "史诗"
        self.install(self.equipment("备用武器"))
        self.assertIn(self.click.call_args.args[2], (0.310, 0.710))
        self.task.click_box.assert_not_called()

    def test_strict_selects_listed_reward_over_unlisted(self):
        self.select([self.equipment("未配置装备"), self.equipment()])
        self.click.assert_called_once_with(self.task, 0.521, 0.600)
        self.task.click_box.assert_not_called()

    def test_strict_selects_listed_reward_for_live_quality_check(self):
        self.task.member_status["equipment"]["names"][0] = "目标武器"
        self.select([self.equipment("未配置装备"), self.equipment(quality="史诗")])
        self.click.assert_called_once_with(self.task, 0.521, 0.600)

    def test_strict_unlisted_rewards_are_refined_directly_when_possible(self):
        self.assertTrue(self.select([self.equipment("杂物甲"), self.equipment("杂物乙")]))
        self.assert_refined()

    def test_strict_enters_install_page_to_refine_when_selection_has_no_refine_button(self):
        self.task.all_texts = [box("选择")]
        self.select([self.equipment("杂物甲"), self.equipment("杂物乙")])
        self.click.assert_called_once_with(self.task, 0.518, 0.454)
        self.task.click_box.assert_not_called()

    def test_strict_shop_cancels_equipment_unneeded_by_target(self):
        cancel, purchase = box("取消", x=300), box("购买", x=920)
        self.task.all_texts = [cancel, purchase, box("100", x=700)]
        self.assertTrue(self.install(self.equipment("未配置装备")))
        self.task.click_box.assert_called_once_with(cancel)
        self.click.assert_not_called()

    def test_strict_shop_buys_listed_upgrade_for_target(self):
        cancel, purchase = box("取消", x=300), box("购买", x=920)
        self.task.all_texts = [cancel, purchase, box("100", x=700)]
        self.assertTrue(self.install(self.equipment()))
        self.click.assert_called_once_with(self.task, 0.756, 0.510)
        self.task.click_box.assert_called_once_with(purchase)

    def test_shop_does_not_reopen_canceled_equipment_and_refresh_clears_rejection(self):
        self.target_index = None
        cancel, purchase = box("取消", x=300), box("购买", x=920)
        self.task.all_texts = [cancel, purchase, box("100", x=700)]
        self.install(self.equipment())
        self.task.click_box.assert_called_once_with(cancel)
        self.assertEqual(self.task.node_status["rejected_shop_equipment"], ["目标武器"])
        self.task.click_box.reset_mock()

        def browse():
            with patch.object(utils, "find_box_at_point", side_effect=[None, box("售罄"), box("100")]), \
                    patch.object(utils, "_get_current_credit", return_value=500), \
                    patch.object(utils, "_get_region_text", return_value="目标武器"), \
                    patch.object(self.task, "find_feature", side_effect=[[box("图标", x=200, y=800)], [], [], []]):
                return utils.handle_shop(self.task)

        self.task.all_texts = []
        self.assertFalse(browse())
        self.task.click_box.assert_not_called()
        free = box("免费", x=100)
        self.task.all_texts = [free]
        self.assertTrue(browse())
        self.task.click_box.assert_called_once_with(free)
        self.assertNotIn("rejected_shop_equipment", self.task.node_status)


if __name__ == "__main__":
    unittest.main()
