"""
アクションのデータ定義
"""
from dataclasses import dataclass, field
from typing import Literal, Optional
import time
from pynput import mouse, keyboard

mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

@dataclass
class Action:
    """個々のアクションを定義するデータクラス"""
    type: Literal['click', 'key', 'loop_start', 'loop_end']
    # 共通設定
    duration: float = 0.0  # 押下時間（秒）
    interval: float = 0.1  # 次の操作までの間隔（秒）
    
    # クリック用
    x: Optional[int] = None
    y: Optional[int] = None
    button: str = 'left'   # left, right, middle
    
    # キー入力用
    key: Optional[str] = None

    # ループ用
    loop_count: int = 1

    def execute(self):
        """定義されたアクションを実行する"""
        if self.type == 'click':
            self._execute_click()
        elif self.type == 'key':
            self._execute_key()
        # loop_start, loop_end は engine 側で処理するため、ここでは何もしない


    def _execute_click(self):
        """クリックアクションを実行する"""
        mouse_controller.position = (self.x, self.y)
        time.sleep(0.05)  # マウスカーソルが移動するのを少し待つ

        pynput_button = getattr(mouse.Button, self.button)

        if self.duration > 0:
            mouse_controller.press(pynput_button)
            time.sleep(self.duration)
            mouse_controller.release(pynput_button)
        else:
            mouse_controller.click(pynput_button, 1)

    def _execute_key(self):
        """キー入力アクションを実行する"""
        try:
            # 'enter', 'ctrl' などの特殊キーの場合
            key_to_press = getattr(keyboard.Key, self.key)
        except (AttributeError, TypeError):
            # 'a', 'b' などの通常キーの場合
            key_to_press = self.key

        if self.duration > 0:
            keyboard_controller.press(key_to_press)
            time.sleep(self.duration)
            keyboard_controller.release(key_to_press)
        else:
            keyboard_controller.press(key_to_press)
            keyboard_controller.release(key_to_press)

    def __str__(self):
        """リスト表示用の文字列表現"""
        if self.type == 'click':
            return f"[Click] {self.button} at ({self.x}, {self.y}) | {self.duration}s / {self.interval}s"
        elif self.type == 'key':
            return f"[Key] {self.key} | {self.duration}s / {self.interval}s"
        elif self.type == 'loop_start':
            return f"--- Loop Start ({self.loop_count} times) ---"
        elif self.type == 'loop_end':
            return "--- Loop End ---"
        return "Unknown Action"
