"""界面调试截图。

全局配置「界面调试 / 每个界面截图」打开后，卡厄思、出击、剧情模式
每次进入一个新的游戏界面，都会把进入前的画面保存到 page_screenshots。
该目录独立于 screenshots，启动时不会被清空。
"""

import os
import re
import sys
from datetime import datetime

import cv2
import numpy as np

PAGE_DEBUG_CONFIG = "界面调试"
PAGE_DEBUG_OPTION = "每个界面截图"
PAGE_SCREENSHOT_DIR = "page_screenshots"
UNRECOGNIZED_PAGE = "未识别界面"
# 未识别画面相对上一张已保存图的变化比例达到该值时，再存一张。
_UNRECOGNIZED_CHANGE_THRESHOLD = 0.30
_INVALID_FILENAME = re.compile(r'[\\/*?:"<>|]')


def reset_page_debug(task):
    """清空界面去重状态，让下次进入同一界面时重新截图。"""
    task._page_debug_last_name = None
    task._page_debug_frame = None
    task._page_debug_last_gray = None


def page_debug_enabled(task) -> bool:
    """读取全局配置。配置不存在或任务还没接上执行器时视为关闭。"""
    getter = getattr(task, "get_global_config", None)
    if not callable(getter):
        return False
    try:
        config = getter(PAGE_DEBUG_CONFIG)
        get = getattr(config, "get", None)
        if not callable(get):
            return False
        return get(PAGE_DEBUG_OPTION, False) is True
    except Exception:
        return False


def dispatch_page_handlers(task, handlers) -> bool:
    """按顺序执行页面处理函数。命中时保存该界面截图并返回 True。"""
    _remember_page_frame(task)
    for handle_page in handlers:
        if handle_page(task):
            save_page_screenshot(task, _handler_name(handle_page))
            return True
    save_page_screenshot(task, UNRECOGNIZED_PAGE)
    return False


def save_page_screenshot(task, page_name):
    """保存当前循环开始时的画面。保存失败不影响页面处理。"""
    try:
        _save_page_screenshot(task, page_name)
    except Exception as error:
        _log(task, f"界面调试截图保存失败: {page_name} ({error})", error=True)


def _remember_page_frame(task):
    if not page_debug_enabled(task):
        reset_page_debug(task)
        return
    frame = _current_frame(task)
    if not isinstance(frame, np.ndarray):
        task._page_debug_frame = None
        return
    try:
        task._page_debug_frame = frame.copy()
    except Exception:
        task._page_debug_frame = None


def _save_page_screenshot(task, page_name):
    if not page_debug_enabled(task):
        return
    if not isinstance(page_name, str) or not page_name.strip():
        page_name = UNRECOGNIZED_PAGE
    frame = getattr(task, "_page_debug_frame", None)
    if not isinstance(frame, np.ndarray):
        return
    last_name = getattr(task, "_page_debug_last_name", None)
    if last_name == page_name and not _should_save_same_page(task, page_name, frame):
        return

    image = _apply_processor(frame)
    mode_name = getattr(task, "name", None)
    if not isinstance(mode_name, str) or not mode_name.strip():
        mode_name = "task"
    folder = os.path.join(
        _screenshot_root(),
        _safe_component(mode_name),
        _safe_component(page_name),
    )
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    path = os.path.join(folder, f"{stamp}.png")
    sequence = 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{stamp}-{sequence}.png")
        sequence += 1
    _write_png(path, image)
    task._page_debug_last_name = page_name
    task._page_debug_last_gray = _small_gray(image)
    _log(task, f"界面调试截图已保存: {page_name} -> {path}")


def _should_save_same_page(task, page_name, frame) -> bool:
    """同一处理函数连续命中时不重复保存。未识别画面变化很大时再存一张。"""
    if page_name != UNRECOGNIZED_PAGE:
        return False
    last_gray = getattr(task, "_page_debug_last_gray", None)
    gray = _small_gray(frame)
    if last_gray is None or last_gray.shape != gray.shape:
        return True
    difference = cv2.absdiff(gray, last_gray)
    _, mask = cv2.threshold(difference, 30, 255, cv2.THRESH_BINARY)
    change_ratio = cv2.countNonZero(mask) / float(gray.shape[0] * gray.shape[1])
    return change_ratio >= _UNRECOGNIZED_CHANGE_THRESHOLD


def _current_frame(task):
    candidates = []
    executor = getattr(task, "executor", None)
    nullable = getattr(executor, "nullable_frame", None)
    if callable(nullable):
        try:
            candidates.append(nullable())
        except Exception:
            pass
    try:
        candidates.append(getattr(task, "frame", None))
    except Exception:
        pass
    for frame in candidates:
        if isinstance(frame, np.ndarray):
            return frame
    return None


def _screenshot_root() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.getcwd()
    return os.path.abspath(os.path.join(base, PAGE_SCREENSHOT_DIR))


def _screenshot_processor():
    try:
        from ok import og
    except Exception:
        return None
    config = getattr(og, "config", None)
    if config is None:
        return None
    try:
        processor = config.get("screenshot_processor")
    except Exception:
        return None
    return processor if callable(processor) else None


def _apply_processor(frame):
    processor = _screenshot_processor()
    if processor is None:
        return frame
    try:
        processed = processor(frame.copy())
    except Exception:
        return frame
    if isinstance(processed, np.ndarray):
        return processed
    return frame


def _small_gray(frame):
    height, width = frame.shape[:2]
    small = cv2.resize(frame, (max(1, width // 4), max(1, height // 4)))
    if small.ndim == 2:
        return small
    return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)


def _write_png(path, image):
    # Windows 上 cv2.imwrite 不能写中文路径，改用 imencode 再落盘。
    encoded, buffer = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("png encode failed")
    buffer.tofile(path)


def _handler_name(handle_page) -> str:
    name = getattr(handle_page, "__name__", "")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "page"


def _safe_component(name: str) -> str:
    cleaned = _INVALID_FILENAME.sub("_", str(name)).strip().rstrip(".")
    return cleaned or "page"


def _log(task, message, error=False):
    logger = getattr(task, "logger", None)
    method = getattr(logger, "warning" if error else "info", None)
    if not callable(method):
        return
    try:
        method(message)
    except Exception:
        pass
