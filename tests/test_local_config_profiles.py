"""本地配置新增与覆盖的纯逻辑验证，不启动界面。"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import config_io


class TestLocalConfigProfiles(unittest.TestCase):
    def setUp(self):
        self.store = {
            "chaos": {
                "甲": {"闪光优先级": ["旧甲"]},
                "乙": {"闪光优先级": ["旧乙"]},
            },
            "sortie": {
                "甲": {"出牌优先级": ["保持"]},
            },
        }

    def test_add_appends_named_profile_without_touching_other_mode(self):
        updated = config_io.add_named_local_profile(
            self.store,
            "chaos",
            "  丙  ",
            {"闪光优先级": ["新丙"]},
        )

        self.assertEqual(list(updated["chaos"]), ["甲", "乙", "丙"])
        self.assertEqual(updated["chaos"]["甲"], {"闪光优先级": ["旧甲"]})
        self.assertEqual(updated["chaos"]["丙"], {"闪光优先级": ["新丙"]})
        self.assertEqual(updated["sortie"], self.store["sortie"])
        self.assertNotIn("丙", self.store["chaos"])

        sortie_updated = config_io.add_named_local_profile(
            self.store,
            "sortie",
            "乙",
            {"出牌优先级": ["新乙"]},
        )
        self.assertEqual(list(sortie_updated["sortie"]), ["甲", "乙"])
        self.assertEqual(sortie_updated["chaos"]["乙"], {"闪光优先级": ["旧乙"]})

    def test_add_creates_first_profile_for_empty_or_invalid_mode(self):
        created = config_io.add_named_local_profile(
            {},
            "chaos",
            "第一份",
            {"游戏语言": "简体中文"},
        )
        replaced = config_io.add_named_local_profile(
            {"chaos": "损坏", "sortie": {"保持": {"v": 1}}},
            "chaos",
            "第一份",
            {"游戏语言": "简体中文"},
        )

        self.assertEqual(created, {"chaos": {"第一份": {"游戏语言": "简体中文"}}})
        self.assertEqual(
            replaced,
            {
                "chaos": {"第一份": {"游戏语言": "简体中文"}},
                "sortie": {"保持": {"v": 1}},
            },
        )

    def test_add_rejects_empty_or_duplicate_names(self):
        original = copy.deepcopy(self.store)

        with self.assertRaises(config_io.LocalProfileSaveError) as empty_name:
            config_io.add_named_local_profile(self.store, "chaos", "   ", {"v": 1})
        with self.assertRaises(config_io.LocalProfileSaveError) as duplicate_name:
            config_io.add_named_local_profile(self.store, "chaos", " 甲 ", {"v": 2})
        with self.assertRaises(config_io.LocalProfileSaveError) as other_mode_ok:
            config_io.add_named_local_profile(self.store, "sortie", "甲", {"v": 3})

        self.assertEqual(str(empty_name.exception), "配置名称不能为空。")
        self.assertEqual(
            str(duplicate_name.exception),
            "本地配置“甲”已存在。请覆盖该配置，或换一个名称。",
        )
        self.assertIn("请覆盖该配置", str(other_mode_ok.exception))
        self.assertEqual(self.store, original)

    def test_overwrite_replaces_settings_and_keeps_name_and_order(self):
        updated = config_io.overwrite_named_local_profile(
            self.store,
            "chaos",
            "甲",
            {"闪光优先级": ["新甲"]},
        )

        self.assertEqual(list(updated["chaos"]), ["甲", "乙"])
        self.assertEqual(updated["chaos"]["甲"], {"闪光优先级": ["新甲"]})
        self.assertEqual(updated["chaos"]["乙"], {"闪光优先级": ["旧乙"]})
        self.assertEqual(updated["sortie"]["甲"], {"出牌优先级": ["保持"]})
        self.assertEqual(self.store["chaos"]["甲"], {"闪光优先级": ["旧甲"]})

    def test_overwrite_missing_profile_does_not_create_one(self):
        original = copy.deepcopy(self.store)

        with self.assertRaises(config_io.LocalProfileSaveError) as missing:
            config_io.overwrite_named_local_profile(
                self.store,
                "chaos",
                "不存在",
                {"v": 1},
            )
        with self.assertRaises(config_io.LocalProfileSaveError):
            config_io.overwrite_named_local_profile(
                self.store,
                "chaos",
                "甲 ",
                {"v": 1},
            )

        self.assertEqual(str(missing.exception), "本地配置“不存在”不存在，无法覆盖。")
        self.assertEqual(self.store, original)
        self.assertNotIn("不存在", self.store["chaos"])


if __name__ == "__main__":
    unittest.main()
