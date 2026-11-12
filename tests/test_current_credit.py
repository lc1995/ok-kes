"""右上角信用点读取离线验证，坐标取自 1600x900 实机截图的 OCR 结果。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ok_tasks"))

import utils


def _text(name, x0, x1, y0, y1, width=1600, height=900):
    box = Mock(x=x0 * width, y=y0 * height, width=(x1 - x0) * width, height=(y1 - y0) * height)
    box.name = name
    return box


class TestCurrentCredit(unittest.TestCase):
    def setUp(self):
        self.task = Mock()
        self.task.width = 1600
        self.task.height = 900

    def test_shop_credit_is_read_beside_crystal_count(self):
        self.task.all_texts = [
            _text("1159/1159", 0.171, 0.253, 0.026, 0.051),
            _text("8", 0.600, 0.613, 0.039, 0.064),
            _text("1014", 0.674, 0.714, 0.033, 0.068),
            _text("80", 0.705, 0.735, 0.300, 0.340),
        ]
        self.assertEqual(utils._get_current_credit(self.task), 1014)

    def test_crystal_count_is_not_taken_as_credit(self):
        self.task.all_texts = [_text("128", 0.590, 0.613, 0.039, 0.064)]
        self.assertEqual(utils._get_current_credit(self.task), 0)


if __name__ == "__main__":
    unittest.main()
