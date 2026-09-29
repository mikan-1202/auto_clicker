"""
アクションのデータ定義
"""

import math
import time
from dataclasses import dataclass
from functools import cache
from threading import TIMEOUT_MAX
from typing import Literal, Optional

from pynput import keyboard, mouse

from .settings import valid_key

CURSOR_SETTLE_SECONDS = 0.05


@cache
def get_mouse_controller():
    return mouse.Controller()


@cache
def get_keyboard_controller():
    return keyboard.Controller()


def wait(seconds, stop_event=None):
    if stop_event is not None:
        return stop_event.wait(seconds)
    time.sleep(seconds)
    return False


@dataclass
class Action:
    """個々のアクションを定義するデータクラス"""

    type: Literal["click", "key", "loop_start", "loop_end"]
    # 共通設定
    duration: float = 0.0  # 押下時間（秒）
    interval: float = 0.1  # 次の操作までの間隔（秒）

    # クリック用
    x: Optional[int] = None
    y: Optional[int] = None
    button: str = "left"  # left, right, middle

    # キー入力用
    key: Optional[str] = None

    # ループ用
    loop_count: int = 1

    def __post_init__(self):
        self.validate()

    def validate(self):
        if self.type not in ("click", "key", "loop_start", "loop_end"):
            raise ValueError("不明なアクション種別です。")
        for value in (self.duration, self.interval):
            if (
                type(value) not in (int, float)
                or not 0 <= value <= TIMEOUT_MAX
                or not math.isfinite(value)
            ):
                raise ValueError("時間は0以上でOSの待機上限以下の有限の数値を指定してください。")
        if self.type == "click":
            if type(self.x) is not int or type(self.y) is not int:
                raise ValueError("座標は整数で指定してください。")
            if self.button not in ("left", "right", "middle"):
                raise ValueError("クリックボタンが不正です。")
        if self.type == "key" and not valid_key(self.key):
            raise ValueError("入力するキーが不正です。")
        if self.type == "loop_start" and (type(self.loop_count) is not int or self.loop_count < 1):
            raise ValueError("繰り返し回数は1以上の整数で指定してください。")

    def execute(self, stop_event=None):
        """定義されたアクションを実行する"""
        if stop_event is not None and stop_event.is_set():
            return
        if self.type == "click":
            self._execute_click(stop_event)
        elif self.type == "key":
            self._execute_key(stop_event)
        # loop_start, loop_end は engine 側で処理するため、ここでは何もしない

    def _execute_click(self, stop_event=None):
        """クリックアクションを実行する"""
        mouse_controller = get_mouse_controller()
        mouse_controller.position = (self.x, self.y)
        if wait(CURSOR_SETTLE_SECONDS, stop_event):
            return

        pynput_button = getattr(mouse.Button, self.button)

        if self.duration > 0:
            mouse_controller.press(pynput_button)
            try:
                wait(self.duration, stop_event)
            finally:
                mouse_controller.release(pynput_button)
        else:
            mouse_controller.click(pynput_button, 1)

    def _execute_key(self, stop_event=None):
        """キー入力アクションを実行する"""
        keyboard_controller = get_keyboard_controller()
        try:
            # 'enter', 'ctrl' などの特殊キーの場合
            key_to_press = getattr(keyboard.Key, self.key)
        except (AttributeError, TypeError):
            # 'a', 'b' などの通常キーの場合
            key_to_press = self.key

        keyboard_controller.press(key_to_press)
        try:
            if self.duration > 0:
                wait(self.duration, stop_event)
        finally:
            keyboard_controller.release(key_to_press)

    def __str__(self):
        """リスト表示用の文字列表現"""
        if self.type == "click":
            return f"[Click] {self.button} at ({self.x}, {self.y}) | {self.duration}s / {self.interval}s"
        elif self.type == "key":
            return f"[Key] {self.key} | {self.duration}s / {self.interval}s"
        elif self.type == "loop_start":
            return f"--- Loop Start ({self.loop_count} times) ---"
        elif self.type == "loop_end":
            return "--- Loop End ---"
        return "Unknown Action"
