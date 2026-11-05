"""赛内克图斯独立眼部模板；不复用特殊怪物 secret_enemy。"""
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np


THRESHOLD = 0.75


class OctopusMatch(NamedTuple):
    confidence: float
    x: int
    y: int
    width: int
    height: int


@lru_cache(maxsize=1)
def _templates():
    path = Path(__file__).parent / "assets" / "octopus_eye.png"
    source = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if source is None:
        raise RuntimeError(f"无法读取章鱼模板：{path}")
    # 固定分析宽度，兼容游戏分辨率；缓存不同大小的灰度模板。
    return tuple(
        cv2.cvtColor(cv2.resize(source, None, fx=scale, fy=scale), cv2.COLOR_BGR2GRAY)
        for scale in np.arange(0.40, 2.41, 0.04)
    )


def match_octopus(frame):
    """返回敌方区域的最高匹配分数和原画面坐标，调用者判断阈值。"""
    if frame is None or frame.size == 0:
        return None
    height, width = frame.shape[:2]
    ratio = 1280 / width
    resized = cv2.resize(frame, (1280, round(height * ratio)))
    h, w = resized.shape[:2]
    x0, y0 = int(w * 0.496), int(h * 0.154)
    region = resized[y0:int(h * 0.636), x0:int(w * 0.967)]
    if region.size == 0:
        return None
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    best = None
    for template in _templates():
        th, tw = template.shape[:2]
        if th > gray.shape[0] or tw > gray.shape[1]:
            continue
        _, score, _, location = cv2.minMaxLoc(
            cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        )
        if best is None or score > best.confidence:
            best = OctopusMatch(float(score), round((location[0] + x0) / ratio),
                                round((location[1] + y0) / ratio),
                                round(tw / ratio), round(th / ratio))
    return best
