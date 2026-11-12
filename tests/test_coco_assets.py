import json
import unittest
from pathlib import Path

import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parents[1] / "ok_tasks" / "assets"


class CocoAssetsTest(unittest.TestCase):
    def test_images_are_full_1080p_screenshots(self):
        data = json.loads((ASSETS / "coco_annotations.json").read_text(encoding="utf-8"))
        for image in data["images"]:
            with self.subTest(image=image["file_name"]):
                # FeatureSet 按整张图缩放到窗口分辨率，小图会被放大到超过搜索区域。
                self.assertEqual((image["width"], image["height"]), (1920, 1080))
                mat = cv2.imdecode(np.fromfile(ASSETS / image["file_name"], dtype=np.uint8), cv2.IMREAD_COLOR)
                self.assertIsNotNone(mat)
                self.assertEqual(mat.shape[:2], (1080, 1920))


if __name__ == "__main__":
    unittest.main()
