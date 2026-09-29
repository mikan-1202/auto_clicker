import tkinter as tk
from tkinter import messagebox, ttk

from ..core.actions import Action
from ..utils import get_key_str
from .widgets import CustomScale


class ActionForm(ttk.Frame):
    """アクション設定フォームを管理するウィジェット"""

    def __init__(self, parent, settings, on_add_callback, on_cancel_callback):
        super().__init__(parent)
        self.settings = settings
        self.on_add_callback = on_add_callback
        self.on_cancel_callback = on_cancel_callback
        self.is_capturing_key = False
        self.captured_key = None
        self.var_duration = tk.DoubleVar(value=0.0)
        self.var_interval = tk.DoubleVar(value=0.1)

        self._init_ui()

    def _init_ui(self):
        # アクションタイプ選択
        type_frame = ttk.Frame(self)
        type_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=2)

        self.var_type = tk.StringVar(value="click")
        self.type_buttons = {}
        types = [("クリック", "click"), ("キー", "key"), ("ループ", "loop")]
        for i, (text, val) in enumerate(types):
            btn = ttk.Button(type_frame, text=text, command=lambda v=val: self._set_action_type(v))
            btn.grid(row=0, column=i, sticky="ew", padx=1)
            type_frame.columnconfigure(i, weight=1)
            self.type_buttons[val] = btn

        # 詳細設定エリア（可変）
        self.details_frame = ttk.Frame(self)
        self.details_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        self.details_frame.columnconfigure(1, weight=1)

        # 初期表示
        self._create_click_form()
        self._update_type_buttons()

        # 共通設定
        ttk.Separator(self).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        self._create_styled_scale(
            text="継続時間(秒):",
            row=3,
            variable=self.var_duration,
            from_=0.0,
            to=5.0,
            on_scale_change=self._on_duration_scale_change,
        )

        self._create_styled_scale(
            text="待機間隔(秒):",
            row=4,
            variable=self.var_interval,
            from_=0.0,
            to=5.0,
            on_scale_change=self._on_interval_scale_change,
        )

        # ボタン
        self.btn_add = ttk.Button(self, text="追加", command=self._on_add)
        self.btn_add.grid(row=5, column=0, columnspan=2, pady=10, sticky="ew")
        self.btn_cancel = ttk.Button(self, text="編集キャンセル", command=self._on_cancel)
        # btn_cancelは編集モード時のみ表示

        self.columnconfigure(1, weight=1)

    def _create_styled_scale(self, text, row, variable, from_, to, on_scale_change):
        """目盛り付きのカスタムスライダーウィジェットを作成して配置する"""
        ttk.Label(self, text=text).grid(row=row, column=0, sticky="w")

        container = ttk.Frame(self)
        container.grid(row=row, column=1, sticky="ew")
        container.columnconfigure(1, weight=1)

        entry = ttk.Entry(container, textvariable=variable, width=5)
        entry.pack(side="left")

        scale_area = ttk.Frame(container)
        scale_area.pack(side="left", fill="x", expand=True, padx=(5, 0))
        scale_area.columnconfigure(0, weight=1)

        # カスタムスライダーを使用
        scale = CustomScale(
            scale_area, from_=from_, to=to, variable=variable, command=on_scale_change
        )
        scale.grid(row=0, column=0, sticky="ew", pady=(2, 0))

    def _set_action_type(self, type_value):
        self.var_type.set(type_value)
        self._update_form_content()

    def _update_type_buttons(self):
        current = self.var_type.get()
        if current == "loop_start":
            current = "loop"
        for val, btn in self.type_buttons.items():
            state = ["pressed", "disabled"] if val == current else ["!pressed", "!disabled"]
            btn.state(state)

    def _update_form_content(self):
        self.is_capturing_key = False
        self._update_type_buttons()
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        action_type = self.var_type.get()
        if action_type == "click":
            self._create_click_form()
        elif action_type == "key":
            self._create_key_form()
        elif action_type in ("loop", "loop_start"):
            self._create_loop_form()
        elif action_type == "loop_end":
            self._create_loop_end_form()

    def _create_click_form(self):
        btn_frame = ttk.Frame(self.details_frame)
        btn_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.var_button = tk.StringVar(value="left")
        self.click_btns = {}
        for val, text in [("left", "左クリック"), ("right", "右クリック")]:
            btn = ttk.Button(btn_frame, text=text, command=lambda v=val: self._set_click_btn(v))
            btn.pack(side="left", fill="x", expand=True, padx=1)
            self.click_btns[val] = btn
        self._set_click_btn("left")

        ttk.Label(self.details_frame, text="X座標:").grid(row=1, column=0, sticky="w")
        self.entry_x = ttk.Entry(self.details_frame)
        self.entry_x.grid(row=1, column=1, sticky="ew")
        ttk.Label(self.details_frame, text="Y座標:").grid(row=2, column=0, sticky="w")
        self.entry_y = ttk.Entry(self.details_frame)
        self.entry_y.grid(row=2, column=1, sticky="ew")

    def _set_click_btn(self, val):
        self.var_button.set(val)
        for v, btn in self.click_btns.items():
            state = ["pressed", "disabled"] if v == val else ["!pressed", "!disabled"]
            btn.state(state)

    def _create_key_form(self):
        self.captured_key = None
        self.btn_capture = ttk.Button(
            self.details_frame, text="キーを設定", command=self.start_key_capture
        )
        self.btn_capture.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(
            self.details_frame, text="上のボタンを押してキーを入力してください", foreground="gray"
        ).grid(row=1, column=0, columnspan=2, sticky="w")

    def _create_loop_form(self):
        ttk.Label(self.details_frame, text="繰り返し回数:").grid(row=0, column=0, sticky="w")
        self.entry_loop = ttk.Entry(self.details_frame)
        self.entry_loop.insert(0, "2")
        self.entry_loop.grid(row=0, column=1, sticky="ew")

    def _create_loop_end_form(self):
        ttk.Label(self.details_frame, text="ループの終点を示します").grid(
            row=0, column=0, columnspan=2
        )

    def start_key_capture(self):
        self.is_capturing_key = True
        self.btn_capture.config(text="キーを押してください...")
        self.focus_set()

    def receive_key(self, key):
        """外部からキー入力を受け取る"""
        key_str = get_key_str(key)
        if key_str:
            # ホットキーとの重複チェック
            if self._is_hotkey_conflict(key_str):
                messagebox.showerror(
                    "エラー",
                    f"キー '{key_str.upper()}' はホットキーとして設定されているため使用できません。",
                )
                self.is_capturing_key = False
                if self.captured_key:
                    self.btn_capture.config(text=f"設定キー: {self.captured_key.upper()}")
                else:
                    self.btn_capture.config(text="キーを設定")
                return

            self.captured_key = key_str
            self.btn_capture.config(text=f"設定キー: {key_str.upper()}")
        self.is_capturing_key = False

    def _is_hotkey_conflict(self, key_str):
        """指定されたキーがホットキーとして設定されているか確認"""
        current = key_str.lower()
        hotkeys = [
            self.settings.start_key,
            self.settings.stop_key,
            self.settings.add_left_key,
            self.settings.add_right_key,
        ]
        return current in [k.lower() for k in hotkeys]

    def _on_duration_scale_change(self, value_str):
        self.var_duration.set(round(float(value_str), 1))

    def _on_interval_scale_change(self, value_str):
        self.var_interval.set(round(float(value_str), 1))

    def _on_add(self):
        try:
            action = self._build_action()
            self.on_add_callback(action)
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("入力エラー", str(e))

    def _on_cancel(self):
        self.on_cancel_callback()

    def _build_action(self):
        action_type = self.var_type.get()
        duration = self.var_duration.get()
        interval = self.var_interval.get()

        if action_type == "click":
            x = int(self.entry_x.get() or 0)
            y = int(self.entry_y.get() or 0)
            return Action(
                type="click",
                duration=duration,
                interval=interval,
                x=x,
                y=y,
                button=self.var_button.get(),
            )
        elif action_type == "key":
            if not self.captured_key:
                raise ValueError("キーを設定してください")
            return Action(type="key", duration=duration, interval=interval, key=self.captured_key)
        elif action_type == "loop" or action_type == "loop_start":
            return Action(type="loop_start", loop_count=int(self.entry_loop.get()), interval=0)
        elif action_type == "loop_end":
            return Action(type="loop_end", interval=0)
        raise ValueError("不明なタイプ")

    def load_action(self, action):
        self.var_type.set(action.type)
        self._update_form_content()
        self.var_duration.set(action.duration)
        self.var_interval.set(action.interval)

        if action.type == "click":
            self._set_click_btn(action.button)
            self.entry_x.delete(0, tk.END)
            self.entry_x.insert(0, str(action.x))
            self.entry_y.delete(0, tk.END)
            self.entry_y.insert(0, str(action.y))
        elif action.type == "key":
            self.captured_key = action.key
            self.btn_capture.config(text=f"設定キー: {action.key.upper()}")
        elif action.type == "loop_start":
            self.entry_loop.delete(0, tk.END)
            self.entry_loop.insert(0, str(action.loop_count))

        self.btn_add.config(text="変更を適用")
        self.btn_cancel.grid(row=6, column=0, columnspan=2, sticky="ew")

    def reset_form(self):
        self.var_type.set("click")
        self._update_form_content()
        self.var_duration.set(0.0)
        self.var_interval.set(0.1)
        self.btn_add.config(text="追加")
        self.btn_cancel.grid_forget()

    def get_duration(self):
        return self.var_duration.get()

    def get_interval(self):
        return self.var_interval.get()
