"""ホットキーイベントをGUIスレッドへ渡し、マクロの実行状態を管理する。"""

from dataclasses import replace
from queue import Empty, Queue

from pynput import keyboard, mouse

from ..utils import get_key_str
from .engine import MacroEngine
from .presets import validate_actions


class MacroController:
    """公開メソッドとprocess_pendingはGUIスレッドから呼ぶ。"""

    def __init__(self, settings, get_actions_func, callbacks):
        self.settings = settings
        self.get_actions = get_actions_func
        self.callbacks = callbacks
        self.macro_engine = None
        self.key_listener = None
        self.mouse_controller = mouse.Controller()
        self.is_input_blocked = lambda: False
        self.running = False
        self._events = Queue()
        self._pressed = set()
        self._closing = False

    def start_listener(self):
        self.key_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self.key_listener.start()

    def stop_listener(self):
        if self.key_listener:
            self.key_listener.stop()
            self.key_listener.join(timeout=1)

    def _on_key_press(self, key):
        # OSのキーリピートで同じ操作が連続登録されることを防ぐ。
        if key in self._pressed:
            return
        self._pressed.add(key)
        self._events.put(("key", (key, self.mouse_controller.position)))

    def _on_key_release(self, key):
        self._pressed.discard(key)

    def process_pending(self):
        """Tkのafterから呼ぶ。リスナー・実行スレッドではTkを操作しない。"""
        for _ in range(100):
            try:
                event, payload = self._events.get_nowait()
            except Empty:
                break
            if self._closing:
                continue
            if event == "finish":
                if payload.is_alive():
                    self._events.put((event, payload))
                    break
                if payload is self.macro_engine:
                    self.macro_engine = None
                    self.running = False
                    self._notify("on_finish")
                    if payload.error is not None:
                        self._notify("on_error", f"実行に失敗しました: {payload.error}")
            elif event == "key":
                key, position = payload
                key_str = get_key_str(key)
                if self._notify("on_raw_key", key, key_str):
                    continue
                if key_str and not self.is_input_blocked():
                    self._check_hotkeys(key_str, position)

    def _notify(self, name, *args):
        callback = self.callbacks.get(name)
        if callback:
            return callback(*args)
        return None

    def _check_hotkeys(self, input_str, position):
        key = input_str.lower()
        if key == self.settings.stop_key.lower():
            self.stop_macro()
        elif key == self.settings.start_key.lower():
            self.start_macro()
        elif not self.running:
            if key == self.settings.add_left_key.lower():
                self._notify("on_add_click", *map(int, position), "left")
            elif key == self.settings.add_right_key.lower():
                self._notify("on_add_click", *map(int, position), "right")

    def start_macro(self):
        if self.running or self._closing:
            return
        try:
            actions = [replace(action) for action in self.get_actions()]
            if not actions:
                raise ValueError("アクションがありません。")
            validate_actions(actions, self.settings.to_dict())
        except (ValueError, TypeError) as error:
            self._notify("on_error", str(error))
            return
        engine = MacroEngine(actions, on_finish=lambda: self._events.put(("finish", engine)))
        self.macro_engine = engine
        self.running = True
        self._notify("on_start")
        try:
            engine.start()
        except RuntimeError as error:
            self.macro_engine = None
            self.running = False
            self._notify("on_finish")
            self._notify("on_error", str(error))

    def stop_macro(self):
        # 終了通知を受けるまでrunningを維持し、停止中の再開始を防ぐ。
        if self.macro_engine:
            self.macro_engine.stop()

    def close(self):
        """終了要求を送り、入力解放を待ってからGUIを破棄する。"""
        if not self._closing:
            self._closing = True
            self.stop_macro()
            self.stop_listener()
        return self.macro_engine is None or not self.macro_engine.is_alive()
