"""
メインウィンドウの実装
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from dataclasses import asdict
import time
from pynput import mouse, keyboard

# 相対インポートが難しい場合のパス解決用（開発環境に合わせて調整してください）
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.actions import Action
from gui.widgets import DraggableListbox
from core.engine import MacroEngine

class AutoClickerApp(tk.Tk):
    # --- Constants ---
    DEFAULT_START_KEY = "f1"
    DEFAULT_STOP_KEY = "f2"
    DEFAULT_ADD_LEFT_KEY = "f11"
    DEFAULT_ADD_RIGHT_KEY = "f12"

    def __init__(self):
        super().__init__()
        self.title("Auto Clicker Macro")
        self.geometry("800x600")

        self._init_data()
        self._init_listeners()
        self._init_gui()

    def _init_data(self):
        """アプリケーションのデータメンバーを初期化する"""
        self.actions = []  # Actionオブジェクトのリスト
        self.editing_index = None  # 編集中のアクションのインデックス
        self.is_capturing_key = False # キー入力取得モードのフラグ
        self.is_setting_hotkey = False # ホットキー設定ダイアログが開いているかのフラグ
        self.capturing_hotkey_widget = None # ホットキー入力検知対象のウィジェット
        self.macro_engine = None # マクロ実行エンジンインスタンス

        # ホットキー設定
        self.start_key = self.DEFAULT_START_KEY
        self.stop_key = self.DEFAULT_STOP_KEY
        self.add_left_key_str = self.DEFAULT_ADD_LEFT_KEY
        self.add_right_key_str = self.DEFAULT_ADD_RIGHT_KEY

        # プリセット保存先フォルダの設定
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.presets_dir = os.path.join(base_dir, 'presets')
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)

        # 設定ファイルから読み込み
        self._load_config()

    def _init_listeners(self):
        """キーボードとマウスのリスナーを初期化する"""
        self.mouse_controller = mouse.Controller()
        # on_pressイベントハンドラを登録し、リスナーをデーモンスレッドとして開始
        self.key_listener = keyboard.Listener(on_press=self.on_key_press)
        self.key_listener.start()

    def _init_gui(self):
        """GUIの主要コンポーネントを初期化・配置する"""
        self._create_menu()
        self._create_main_layout()

    def destroy(self):
        """アプリケーション終了時にリスナーを停止する"""
        if hasattr(self, 'key_listener') and self.key_listener.is_alive():
            self.key_listener.stop()
            self.key_listener.join() # リスナースレッドが完全に終了するのを待つ
        super().destroy()

    # --- GUI Creation Methods ---

    def _create_menu(self):
        """ウィンドウ上部のメニューバーを作成する"""
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        # ファイルメニュー
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="ファイル", menu=file_menu)
        file_menu.add_command(label="新規作成", command=self._new_preset)
        file_menu.add_command(label="設定を開く", command=self.load_preset)
        file_menu.add_command(label="設定を保存", command=self.save_preset)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.destroy)

        # 編集メニュー
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="編集", menu=edit_menu)
        edit_menu.add_command(label="ホットキー設定...", command=self._open_settings_dialog)

    def _create_main_layout(self):
        """メインのGUIレイアウトを作成する"""
        # 左右分割
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill='both', expand=True, padx=5, pady=5)

        # 左側：設定・追加エリア
        left_panel = ttk.LabelFrame(paned_window, text="アクション設定", padding=10)
        paned_window.add(left_panel, weight=1)
        self._init_input_forms(left_panel)

        # 右側：リストエリア
        right_panel = ttk.LabelFrame(paned_window, text="アクションリスト (D&Dで移動, 右クリック/Deleteで操作)", padding=10)
        paned_window.add(right_panel, weight=2)
        self._init_list_view(right_panel)

    def _init_input_forms(self, parent):
        """左パネルのアクション設定フォームを作成する"""
        # アクションタイプ選択
        ttk.Label(parent, text="種類:").grid(row=0, column=0, sticky='w', pady=2)
        self.var_type = tk.StringVar(value='click')
        type_cb = ttk.Combobox(parent, textvariable=self.var_type, values=('click', 'key', 'wait', 'loop'), state='readonly')
        type_cb.grid(row=0, column=1, sticky='ew', pady=2)
        type_cb.bind('<<ComboboxSelected>>', self._on_type_changed) # イベント引数を渡す

        # 詳細設定エリア（可変）
        self.details_frame = ttk.Frame(parent)
        self.details_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        
        # 初期表示
        self._create_click_form()

        # 共通設定
        ttk.Separator(parent).grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)
        
        ttk.Label(parent, text="継続時間(秒):").grid(row=3, column=0, sticky='w')
        self.entry_duration = ttk.Entry(parent)
        self.entry_duration.insert(0, "0.0")
        self.entry_duration.grid(row=3, column=1, sticky='ew')

        ttk.Label(parent, text="待機間隔(秒):").grid(row=4, column=0, sticky='w')
        self.entry_interval = ttk.Entry(parent)
        self.entry_interval.insert(0, "0.1")
        self.entry_interval.grid(row=4, column=1, sticky='ew')

        # ボタン
        self.btn_add = ttk.Button(parent, text="追加", command=self.add_action_from_form)
        self.btn_add.grid(row=5, column=0, columnspan=2, pady=10, sticky='ew')
        self.btn_cancel_edit = ttk.Button(parent, text="編集キャンセル", command=self.cancel_edit) # gridは編集モードで

        # ヒント
        info_text = f"ヒント: {self.add_left_key_str.upper()}で左クリック、{self.add_right_key_str.upper()}で右クリックをリストに直接追加"
        self.info_label = ttk.Label(parent, text=info_text, justify=tk.LEFT, wraplength=250)
        self.info_label.grid(row=7, column=0, columnspan=2, pady=(10, 0), sticky='w')

    def _init_list_view(self, parent):
        """右パネルのアクションリストビューを作成する"""
        # スクロールバー
        scrollbar = ttk.Scrollbar(parent)
        scrollbar.pack(side='right', fill='y')

        # リストボックス
        self.listbox = DraggableListbox(parent, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE)
        self.listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.listbox.yview)

        # イベントバインド
        self.listbox.set_reorder_callback(self.on_reorder)
        self.listbox.bind("<Button-3>", self.show_context_menu)
        self.listbox.bind("<Delete>", lambda event: self.delete_selected_action())

        # 右クリックメニュー
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="詳細設定 (編集)", command=self.load_selected_action_to_form)
        self.context_menu.add_command(label="削除", command=self.delete_selected_action)

    # --- Dynamic Form Creation ---

    def _on_type_changed(self, event=None):
        """アクションタイプの変更に応じてフォームを切り替える"""
        action_type = self.var_type.get()
        # 現在のフォームをクリア
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        # 新しいフォームを作成
        if action_type == 'click':
            self._create_click_form()
        elif action_type == 'key':
            self._create_key_form()
        elif action_type == 'wait':
            self._create_wait_form()
        elif action_type == 'loop':
            self._create_loop_form()
        elif action_type == 'loop_start':
            self._create_loop_form() # 編集時も同じフォームを使用
        elif action_type == 'loop_end':
            self._create_loop_end_form()

    def _create_click_form(self):
        """クリックアクション用の設定フォームを作成する"""
        
        ttk.Label(self.details_frame, text="ボタン:").grid(row=0, column=0, sticky='w')
        self.var_button = tk.StringVar(value='left')
        ttk.Combobox(self.details_frame, textvariable=self.var_button, values=('left', 'right', 'middle'), state='readonly').grid(row=0, column=1)

        ttk.Label(self.details_frame, text="タイプ:").grid(row=1, column=0, sticky='w')
        self.var_click_type = tk.StringVar(value='single')
        ttk.Combobox(self.details_frame, textvariable=self.var_click_type, values=('single', 'double'), state='readonly').grid(row=1, column=1)

        ttk.Label(self.details_frame, text="X座標:").grid(row=2, column=0, sticky='w')
        self.entry_x = ttk.Entry(self.details_frame)
        self.entry_x.grid(row=2, column=1)
        
        ttk.Label(self.details_frame, text="Y座標:").grid(row=3, column=0, sticky='w')
        self.entry_y = ttk.Entry(self.details_frame)
        self.entry_y.grid(row=3, column=1)

    def _create_key_form(self):
        """キーアクション用の設定フォームを作成する"""
        ttk.Label(self.details_frame, text="キー:").grid(row=0, column=0, sticky='w')
        self.entry_key = ttk.Entry(self.details_frame)
        self.entry_key.grid(row=0, column=1)

        self.btn_capture_key = ttk.Button(self.details_frame, text="キー入力を取得", command=self._start_key_capture)
        self.btn_capture_key.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        ttk.Label(self.details_frame, text="(例: a, enter, ctrl)", foreground='gray').grid(row=2, column=0, columnspan=2, sticky='w')

    def _create_wait_form(self):
        """待機アクション用の説明を表示する"""
        ttk.Label(self.details_frame, text="※待機時間は共通設定の\n「待機間隔」に入力してください").grid(row=0, column=0, columnspan=2)

    def _create_loop_form(self):
        """ループアクション用の設定フォームを作成する"""
        ttk.Label(self.details_frame, text="繰り返し回数:").grid(row=0, column=0, sticky='w')
        self.entry_loop_count = ttk.Entry(self.details_frame)
        self.entry_loop_count.insert(0, "2") # デフォルト値
        self.entry_loop_count.grid(row=0, column=1)

    def _create_loop_end_form(self):
        """ループ終了アクション用の説明を表示する"""
        ttk.Label(self.details_frame, text="ループの終点を示します。\n対応するループ開始点とペアで使います。").grid(row=0, column=0, columnspan=2)

    # --- Action/Data Handling ---

    def add_action_from_form(self):
        """フォームの内容からアクションを作成または更新する"""
        action_type = self.var_type.get()

        # ループ追加は特別処理
        if action_type == 'loop':
            self._add_loop_around_actions()
            return

        try:
            # 既存のアクションの編集処理、または通常のアクション追加
            action = self._create_action_from_form()
            if self.editing_index is not None:
                self._update_action_in_view(self.editing_index, action)
                self.cancel_edit()
            else:
                self._add_action_to_view(action)

        except (ValueError, TypeError) as e:
            messagebox.showerror("入力エラー", f"入力値が正しくありません。\n{e}")

    def _add_loop_around_actions(self):
        """現在のアクションリスト全体を囲むループを追加する"""
        if not self.actions:
            messagebox.showwarning("追加不可", "アクションリストが空です。ループで囲むアクションがありません。")
            return

        try:
            loop_count = int(self.entry_loop_count.get())
            if loop_count <= 0: raise ValueError()
        except (ValueError, AttributeError):
            messagebox.showerror("入力エラー", "繰り返し回数には1以上の整数を入力してください。")
            return

        start_action = Action(type='loop_start', loop_count=loop_count, interval=0)
        end_action = Action(type='loop_end', interval=0)
        self._add_action_to_view(start_action, index=0)
        self._add_action_to_view(end_action, index=tk.END)

    def _create_action_from_form(self):
        """フォームの入力値からActionオブジェクトを生成する"""
        action_type = self.var_type.get()
        duration = float(self.entry_duration.get())
        interval = float(self.entry_interval.get())

        if action_type == 'click':
            x = int(self.entry_x.get()) if self.entry_x.get() else 0
            y = int(self.entry_y.get()) if self.entry_y.get() else 0
            return Action(type='click', duration=duration, interval=interval,
                          x=x, y=y, button=self.var_button.get(), click_type=self.var_click_type.get())
        elif action_type == 'key':
            key = self.entry_key.get()
            if not key:
                raise ValueError("キーを入力してください。")
            self._validate_hotkey_conflict(key)
            return Action(type='key', duration=duration, interval=interval, key=key)
        elif action_type == 'wait':
            return Action(type='wait', duration=0, interval=interval)
        elif action_type == 'loop_start':
            loop_count = int(self.entry_loop_count.get())
            return Action(type='loop_start', loop_count=loop_count, interval=0) # ループ自体は待機しない
        elif action_type == 'loop_end':
            return Action(type='loop_end', interval=0) # ループ自体は待機しない
        raise ValueError("不明なアクションタイプです。")

    def load_selected_action_to_form(self):
        """選択されたアクションをフォームにロードして編集モードにする"""
        sel = self.listbox.curselection()
        if not sel: return
        
        index = sel[0]
        action = self.actions[index]
        self.editing_index = index

        # フォームに値をセット
        self.var_type.set(action.type)
        self._on_type_changed()
        
        self.entry_duration.delete(0, tk.END); self.entry_duration.insert(0, str(action.duration))
        self.entry_interval.delete(0, tk.END); self.entry_interval.insert(0, str(action.interval))

        if action.type == 'click':
            self.var_button.set(action.button)
            self.var_click_type.set(action.click_type)
            self.entry_x.delete(0, tk.END); self.entry_x.insert(0, str(action.x))
            self.entry_y.delete(0, tk.END); self.entry_y.insert(0, str(action.y))
        elif action.type == 'key':
            self.entry_key.delete(0, tk.END); self.entry_key.insert(0, str(action.key))
        elif action.type == 'loop_start':
            self.entry_loop_count.delete(0, tk.END); self.entry_loop_count.insert(0, str(action.loop_count))

        # UIを編集モードに切り替え
        self.btn_add.config(text="変更を適用")
        self.btn_cancel_edit.grid(row=6, column=0, columnspan=2, sticky='ew')

    def cancel_edit(self):
        """編集モード解除"""
        self.editing_index = None
        self.btn_add.config(text="追加")
        self.btn_cancel_edit.grid_forget()
        # フォームをデフォルト状態に戻す
        self.var_type.set('click')
        self._on_type_changed()

    def delete_selected_action(self):
        """リストで選択されているアクションを削除する"""
        sel = self.listbox.curselection()
        if not sel: return
        index = sel[0]
        self._delete_action_from_view(index)

    def on_reorder(self, old_index, new_index):
        """リストのD&D操作に応じて内部データを並べ替える"""
        item = self.actions.pop(old_index)
        self.actions.insert(new_index, item)

    # --- View Synchronization ---

    def _add_action_to_view(self, action, index=tk.END):
        """データとリストボックスの両方にアクションを追加する"""
        if index == tk.END:
            self.actions.append(action)
        else:
            self.actions.insert(index, action)
        self.listbox.insert(index, str(action))
        self.listbox.see(index) # 追加した項目が見えるようにスクロール

    def _update_action_in_view(self, index, action):
        """データとリストボックスのアクションを更新する"""
        self.actions[index] = action
        self.listbox.delete(index)
        self.listbox.insert(index, str(action))

    def _delete_action_from_view(self, index):
        """データとリストボックスからアクションを削除する"""
        del self.actions[index]
        self.listbox.delete(index)
        if self.editing_index == index:
            self.cancel_edit()

    def _clear_actions_from_view(self):
        """すべてのアクションをデータとリストボックスから削除する"""
        self.actions.clear()
        self.listbox.delete(0, tk.END)
        self.cancel_edit()

    # --- Preset Save/Load ---

    def _new_preset(self):
        """新規作成。現在のリストをクリアする。"""
        # アクションが存在する場合、確認ダイアログを表示
        if self.actions and not messagebox.askyesno("確認", "現在のリストを破棄して新規作成しますか？\n保存されていない変更は失われます。"):
            return
        self._clear_actions_from_view()

    def save_preset(self):
        """現在の設定をJSONファイルに保存する"""
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)

        path = filedialog.asksaveasfilename(
            initialdir=self.presets_dir,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        if not path: return
        
        settings = {
            "start_key": self.start_key,
            "stop_key": self.stop_key,
            "add_left_key": self.add_left_key_str,
            "add_right_key": self.add_right_key_str
        }
        data = {
            "settings": settings,
            "actions": [asdict(a) for a in self.actions]
        }
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("保存", "ファイルを保存しました")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました: {e}")

    def load_preset(self):
        """JSONファイルから設定を読み込む"""
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)

        path = filedialog.askopenfilename(
            initialdir=self.presets_dir,
            filetypes=[("JSON Files", "*.json")]
        )
        if not path: return

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # 設定を読み込み
            settings = data.get("settings", {})
            self.start_key = settings.get("start_key", self.DEFAULT_START_KEY)
            self.stop_key = settings.get("stop_key", self.DEFAULT_STOP_KEY)
            self.add_left_key_str = settings.get("add_left_key", self.DEFAULT_ADD_LEFT_KEY)
            self.add_right_key_str = settings.get("add_right_key", self.DEFAULT_ADD_RIGHT_KEY)
            self._update_info_label()

            # アクションを読み込み
            self._clear_actions_from_view()
            for act_dict in data.get("actions", []):
                act = Action(**act_dict)
                self._add_action_to_view(act)
                
            messagebox.showinfo("読み込み", "ファイルを読み込みました")
        except Exception as e:
            messagebox.showerror("エラー", f"読み込みに失敗しました: {e}")

    # --- Config Handling ---

    def _load_config(self):
        """設定ファイルを読み込む"""
        config_path = "config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.start_key = config.get("start_key", self.start_key)
                    self.stop_key = config.get("stop_key", self.stop_key)
                    self.add_left_key_str = config.get("add_left_key", self.add_left_key_str)
                    self.add_right_key_str = config.get("add_right_key", self.add_right_key_str)
            except Exception as e:
                print(f"設定ファイルの読み込みに失敗しました: {e}")

    def _save_config(self):
        """設定をファイルに保存する"""
        config = {
            "start_key": self.start_key,
            "stop_key": self.stop_key,
            "add_left_key": self.add_left_key_str,
            "add_right_key": self.add_right_key_str
        }
        try:
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"設定ファイルの保存に失敗しました: {e}")

    # --- Hotkey Handling ---

    def on_key_press(self, key):
        """グローバルキー入力イベントを処理する"""
        # ホットキー設定ダイアログでキーキャプチャ中の場合、最優先で処理
        if self.capturing_hotkey_widget:
            key_str = self._get_key_str_from_pynput(key)
            if key_str:
                # GUIの更新はメインスレッドで行う
                self.after(0, self._update_hotkey_button, key_str)
            return # 他のホットキー処理をすべてブロック

        # アクション設定フォームのキー入力取得モードの場合
        if self.is_capturing_key:
            self._capture_key(key)
            return

        # ホットキー設定ダイアログが開いているがキャプチャ中でない場合は、マクロ関連のホットキーを無効化
        if self.is_setting_hotkey:
            return

        key_str = self._get_key_str_from_pynput(key) # ここを修正
        if not key_str: return

        # マクロ開始・停止を最優先でチェック
        self._check_macro_hotkeys(key_str)

    def start_macro(self):
        """マクロの実行を開始する"""
        if self.macro_engine and self.macro_engine.is_alive():
            print("マクロはすでに実行中です。")
            return

        if not self.actions:
            messagebox.showwarning("マクロ開始不可", "実行するアクションが登録されていません。")
            return

        print("マクロを開始します...")
        self.title("Auto Clicker Macro (実行中...)")

        self.macro_engine = MacroEngine(
            actions=self.actions,
            on_finish=lambda: self.after(0, self._on_macro_finish) # 終了時のコールバックを渡す
        )
        self.macro_engine.start()

    def stop_macro(self):
        """実行中のマクロを停止する"""
        if self.macro_engine and self.macro_engine.is_alive():
            print("マクロを停止します...")
            self.macro_engine.stop()
        else:
            print("実行中のマクロはありません。")

    def _on_macro_finish(self):
        """マクロ終了時に呼び出され、GUIの状態をリセットする"""
        print("GUIをリセットします。")
        self.title("Auto Clicker Macro")
        self.macro_engine = None

    def _add_click_action_by_hotkey(self, button_type):
        """ホットキーでクリックアクションを直接追加する"""
        try:
            duration = float(self.entry_duration.get())
            interval = float(self.entry_interval.get())
            click_type = self.var_click_type.get() if self.var_type.get() == 'click' else 'single'
            x, y = self.mouse_controller.position

            action = Action(type='click', duration=duration, interval=interval,
                            x=int(x), y=int(y), button=button_type, click_type=click_type)
            self._add_action_to_view(action)
        except ValueError:
            print("Could not add action via hotkey: Invalid value in form.")
        except Exception as e:
            print(f"Unexpected error adding action via hotkey: {e}")

    def _start_key_capture(self):
        """キー入力取得モードを開始する"""
        self.is_capturing_key = True
        self.btn_capture_key.config(text="キーを押してください...")
        self.focus_set() # 他のウィジェットからフォーカスを外す

    def _capture_key(self, key):
        """押されたキーを取得し、フォームに設定する"""
        key_str = self._get_key_str_from_pynput(key)
        if key_str:
            # GUIの更新はメインスレッドで行う
            self.after(0, self._update_key_entry, key_str)
        self.is_capturing_key = False

    def _update_key_entry(self, key_str):
        """キー入力フォームの値を更新する"""
        self.entry_key.delete(0, tk.END)
        self.entry_key.insert(0, key_str)
        self.btn_capture_key.config(text="キー入力を取得")

    def _update_hotkey_button(self, key_str):
        """ホットキー設定ボタンのテキストを更新し、キャプチャモードを終了する"""
        if self.capturing_hotkey_widget:
            # TODO: ここでキーの重複チェックをリアルタイムで行うとより親切
            self.capturing_hotkey_widget.config(text=key_str)
            self.capturing_hotkey_widget = None

    def _get_key_str_from_pynput(self, key):
        """pynputのKeyオブジェクトを文字列表現に変換する"""
        if isinstance(key, keyboard.Key):
            return key.name
        if isinstance(key, keyboard.KeyCode):
            return key.char
        return None

    def _check_macro_hotkeys(self, input_str):
        """マクロ実行関連のホットキーをチェックして実行する"""
        if not input_str: return

        input_lower = input_str.lower()
        if input_lower == self.start_key.lower():
            self.after(0, self.start_macro)
        elif input_lower == self.stop_key.lower():
            self.after(0, self.stop_macro)
        elif input_lower == self.add_left_key_str.lower():
            self.after(0, lambda: self._add_click_action_by_hotkey('left'))
        elif input_lower == self.add_right_key_str.lower():
            self.after(0, lambda: self._add_click_action_by_hotkey('right'))

    def _update_info_label(self):
        """ホットキーのヒントラベルを現在の設定で更新する"""
        info_text = f"ヒント: {self.add_left_key_str.upper()}で左クリック、{self.add_right_key_str.upper()}で右クリックをリストに直接追加"
        if hasattr(self, 'info_label'):
            self.info_label.config(text=info_text)

    # --- Dialogs and Menus ---

    def show_context_menu(self, event):
        """リストボックスの右クリックメニューを表示する"""
        index = self.listbox.nearest(event.y)
        if index >= 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(index)
            self.context_menu.post(event.x_root, event.y_root)

    def _open_settings_dialog(self):
        """ホットキー設定用のダイアログを開く"""
        dialog = tk.Toplevel(self)
        dialog.title("ホットキー設定")
        dialog.geometry("350x200")
        dialog.resizable(False, False)
        dialog.transient(self) # 親ウィンドウの前面に表示
        dialog.grab_set()      # モーダルにする
        dialog.transient(self)
        dialog.grab_set()

        self.is_setting_hotkey = True
        self.capturing_hotkey_widget = None

        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill="both", expand=True)

        labels = ["マクロ開始:", "マクロ停止:", "左クリック追加:", "右クリック追加:"]
        current_keys = [self.start_key, self.stop_key, self.add_left_key_str, self.add_right_key_str]
        buttons = []

        def start_capture(button):
            if self.capturing_hotkey_widget:
                messagebox.showinfo("情報", "キー入力待機中です。いずれかのキーを押してください。", parent=dialog)
                return
            self.capturing_hotkey_widget = button
            button.config(text="キーを押してください...")

        for i, text in enumerate(labels):
            ttk.Label(frame, text=text).grid(row=i, column=0, sticky="w", pady=5, padx=5)
            button = ttk.Button(frame, text=current_keys[i], width=20)
            button.config(command=lambda b=button: start_capture(b))
            button.grid(row=i, column=1, sticky="ew", pady=5, padx=5)
            buttons.append(button)

        frame.columnconfigure(1, weight=1)

        def on_close():
            self.is_setting_hotkey = False
            self.capturing_hotkey_widget = None
            dialog.destroy()

        def apply_and_close():
            new_keys = [b.cget("text") for b in buttons]
            if not all(new_keys):
                messagebox.showerror("エラー", "すべてのキーを設定してください。", parent=dialog)
                return
            if len(set(k.lower() for k in new_keys)) != len(new_keys):
                messagebox.showerror("エラー", "ホットキーが重複しています。", parent=dialog)
                return

            self.start_key, self.stop_key, self.add_left_key_str, self.add_right_key_str = new_keys
            self._update_info_label()
            self._save_config()
            messagebox.showinfo("設定", "ホットキーを更新しました。", parent=dialog)
            on_close()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(labels), column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="OK", command=apply_and_close).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="キャンセル", command=on_close).pack(side="left", padx=10)
        dialog.protocol("WM_DELETE_WINDOW", on_close)

    # --- Validation ---

    def _validate_hotkey_conflict(self, key_to_check):
        """指定されたキーがホットキーと競合しないか検証する"""
        hotkeys = [
            self.start_key, self.stop_key,
            self.add_left_key_str, self.add_right_key_str
        ]
        if key_to_check.lower() in [h.lower() for h in hotkeys]:
            raise ValueError(f"キー '{key_to_check}' はホットキーとして設定されているため使用できません。")

if __name__ == "__main__":
    app = AutoClickerApp()
    app.mainloop()
