"""
アプリケーションの制御ロジック（Controller）
"""
from pynput import mouse, keyboard
from .engine import MacroEngine
from ..utils import get_key_str

class MacroController:
    def __init__(self, settings, get_actions_func, callbacks):
        self.settings = settings
        self.get_actions = get_actions_func # アクションリストを取得する関数
        self.callbacks = callbacks # UI操作のためのコールバック辞書
        
        self.macro_engine = None
        self.key_listener = None
        self.mouse_controller = mouse.Controller()
        
        # 外部からの入力ブロック判定用関数（デフォルトはブロックなし）
        self.is_input_blocked = lambda: False

    def start_listener(self):
        """キーボード監視を開始する"""
        self.key_listener = keyboard.Listener(on_press=self._on_key_press)
        self.key_listener.start()

    def stop_listener(self):
        """キーボード監視を停止する"""
        if self.key_listener and self.key_listener.is_alive():
            self.key_listener.stop()
            self.key_listener.join()

    def _on_key_press(self, key):
        """キー入力イベントハンドラ"""
        key_str = get_key_str(key)
        
        # 1. 生のキーイベントをUI側に通知（設定ダイアログのキャプチャ用など）
        # UI側で処理された場合（Trueが返った場合）はここで終了
        if self.callbacks.get('on_raw_key'):
            if self.callbacks['on_raw_key'](key, key_str):
                return

        if not key_str:
            return

        # 2. ブロック条件（例：設定ダイアログが開いている）ならホットキー処理しない
        if self.is_input_blocked():
            return

        # 3. マクロ制御ホットキーの判定
        self._check_hotkeys(key_str)

    def _check_hotkeys(self, input_str):
        input_lower = input_str.lower()
        
        if input_lower == self.settings.start_key.lower():
            self.start_macro()
        elif input_lower == self.settings.stop_key.lower():
            self.stop_macro()
        elif input_lower == self.settings.add_left_key.lower():
            self._trigger_add_click('left')
        elif input_lower == self.settings.add_right_key.lower():
            self._trigger_add_click('right')

    def start_macro(self):
        """マクロを開始する"""
        if self.macro_engine and self.macro_engine.is_alive():
            return

        actions = self.get_actions()
        if not actions:
            if self.callbacks.get('on_error'):
                self.callbacks['on_error']("実行するアクションが登録されていません。")
            return

        # UI側に開始を通知（ロック処理など）
        if self.callbacks.get('on_start'):
            self.callbacks['on_start']()

        self.macro_engine = MacroEngine(
            actions=actions,
            on_finish=self._on_macro_finish
        )
        self.macro_engine.start()

    def stop_macro(self):
        """マクロを停止する"""
        if self.macro_engine and self.macro_engine.is_alive():
            self.macro_engine.stop()

    def _on_macro_finish(self):
        """マクロ終了時の処理"""
        self.macro_engine = None
        # UI側に終了を通知（ロック解除など）
        if self.callbacks.get('on_finish'):
            self.callbacks['on_finish']()

    def _trigger_add_click(self, button):
        """クリック追加ホットキーの処理"""
        x, y = self.mouse_controller.position
        if self.callbacks.get('on_add_click'):
            self.callbacks['on_add_click'](int(x), int(y), button)
