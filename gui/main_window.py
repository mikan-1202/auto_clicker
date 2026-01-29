"""
メインウィンドウの実装
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import asdict
import os, sys

from auto_clicker.core.actions import Action
from auto_clicker.core.controller import MacroController
from auto_clicker.core.settings import SettingsManager
from auto_clicker.gui.widgets import DraggableListbox
from auto_clicker.gui.action_form import ActionForm
from auto_clicker.gui.settings_dialog import SettingsDialog
from auto_clicker.utils import load_json, save_json

class AutoClickerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Auto Clicker Macro")
        self.geometry("800x600")
        self.bell = lambda: None # メッセージボックスの通知音を無効化

        self._init_data()
        self._init_listeners()
        self._init_gui()

    def _init_data(self):
        """アプリケーションのデータメンバーを初期化する"""
        self.actions = []  # Actionオブジェクトのリスト
        self.editing_index = None  # 編集中のアクションのインデックス
        self.is_setting_hotkey = False # ホットキー設定ダイアログが開いているかのフラグ
        self.settings_dialog = None # 設定ダイアログのインスタンス

        # アプリケーションのベースパスを決定（開発環境とexe実行環境の両対応）
        if getattr(sys, 'frozen', False):
            # PyInstallerでビルドされた実行可能ファイルの場合
            self.base_dir = os.path.dirname(sys.executable)
        else:
            # 通常のPythonスクリプトとして実行した場合
            self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.presets_dir = os.path.join(self.base_dir, 'presets')
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)
        
        self.settings = SettingsManager(base_path=self.base_dir)

    def _init_listeners(self):
        """キーボードとマウスのリスナーを初期化する"""
        # コントローラーに渡すコールバックを定義
        callbacks = {
            'on_start': lambda: self.after(0, self._on_macro_start_ui),
            'on_finish': lambda: self.after(0, self._on_macro_finish_ui),
            'on_error': lambda msg: self.after(0, lambda: messagebox.showwarning("エラー", msg)),
            'on_add_click': lambda x, y, btn: self.after(0, lambda: self._add_click_action_by_hotkey(x, y, btn)),
            'on_raw_key': self._on_raw_key_callback
        }

        self.controller = MacroController(self.settings, lambda: self.actions, callbacks)
        
        # 入力ブロック条件を設定（ホットキー設定中はマクロホットキーを無効化）
        self.controller.is_input_blocked = lambda: self.is_setting_hotkey

        self.controller.start_listener()

    def _init_gui(self):
        """GUIの主要コンポーネントを初期化・配置する"""
        self._create_menu()
        self._create_main_layout()

    def destroy(self):
        """アプリケーション終了時にリスナーを停止する"""
        if hasattr(self, 'controller'):
            self.controller.stop_listener()
        super().destroy()

    # --- GUI Creation Methods ---

    def _create_menu(self):
        """ウィンドウ上部のメニューバーを作成する"""
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)

        # ファイルメニュー
        self.file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="ファイル", menu=self.file_menu)
        self.file_menu.add_command(label="新規作成", command=self._new_preset)
        self.file_menu.add_command(label="設定を開く", command=self.load_preset)
        self.file_menu.add_command(label="設定を保存", command=self.save_preset)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="終了", command=self.destroy)

        # 編集メニュー
        self.edit_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="編集", menu=self.edit_menu)
        self.edit_menu.add_command(label="ホットキー設定...", command=self._open_settings_dialog)

    def _create_main_layout(self):
        """メインのGUIレイアウトを作成する"""
        # 左右分割
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill='both', expand=True, padx=5, pady=5)

        # 左側：設定・追加エリア
        left_panel = ttk.LabelFrame(paned_window, text="アクション設定", padding=10)
        paned_window.add(left_panel, weight=1)
        
        self.action_form = ActionForm(left_panel, self.settings, self.on_action_add, self.cancel_edit)
        self.action_form.pack(fill='both', expand=True)
        
        self.info_label = ttk.Label(left_panel, justify=tk.LEFT, wraplength=300)
        self.info_label.pack(pady=(10, 0), anchor='w')
        self._update_info_label()

        # 右側：リストエリア
        right_panel = ttk.LabelFrame(paned_window, text="アクションリスト (D&Dで移動, 右クリック/Deleteで操作)", padding=10)
        paned_window.add(right_panel, weight=2)
        self._init_list_view(right_panel)

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

    # --- Action/Data Handling ---

    def on_action_add(self, action):
        """ActionFormからの追加コールバック"""
        if action.type == 'loop_start':
            # ループの場合はペアを追加する特別処理
            if not self.actions:
                messagebox.showwarning("追加不可", "アクションリストが空です。")
                return
            
            start_action = action
            end_action = Action(type='loop_end', interval=0)
            self._add_action_to_view(start_action, index=0)
            self._add_action_to_view(end_action, index=tk.END)
        else:
            if self.editing_index is not None:
                self._update_action_in_view(self.editing_index, action)
                self.cancel_edit()
            else:
                self._add_action_to_view(action)

    def load_selected_action_to_form(self):
        """選択されたアクションをフォームにロードして編集モードにする"""
        sel = self.listbox.curselection()
        if not sel: return
        
        index = sel[0]
        action = self.actions[index]
        self.editing_index = index
        self.action_form.load_action(action)

    def cancel_edit(self):
        """編集モード解除"""
        self.editing_index = None
        self.action_form.reset_form()

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
            "start_key": self.settings.start_key,
            "stop_key": self.settings.stop_key,
            "add_left_key": self.settings.add_left_key,
            "add_right_key": self.settings.add_right_key
        }
        data = {
            "settings": settings,
            "actions": [asdict(a) for a in self.actions]
        }
        try:
            save_json(path, data)
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
            data = load_json(path)

            # 設定を読み込み
            settings = data.get("settings", {})
            self.settings.start_key = settings.get("start_key", self.settings.DEFAULT_START_KEY)
            self.settings.stop_key = settings.get("stop_key", self.settings.DEFAULT_STOP_KEY)
            self.settings.add_left_key = settings.get("add_left_key", self.settings.DEFAULT_ADD_LEFT_KEY)
            self.settings.add_right_key = settings.get("add_right_key", self.settings.DEFAULT_ADD_RIGHT_KEY)
            self._update_info_label()

            # アクションを読み込み
            self._clear_actions_from_view()
            for act_dict in data.get("actions", []):
                act = Action(**act_dict)
                self._add_action_to_view(act)
                
            messagebox.showinfo("読み込み", "ファイルを読み込みました")
        except Exception as e:
            messagebox.showerror("エラー", f"読み込みに失敗しました: {e}")

    # --- Hotkey Handling ---

    def _on_raw_key_callback(self, key, key_str):
        """
        コントローラーから受け取った生のキー入力イベント。
        設定ダイアログでのキーキャプチャなどに使用する。
        戻り値: Trueなら処理済みとしてコントローラー側の処理を中断させる。
        """
        # 1. ホットキー設定ダイアログでキーキャプチャ中の場合
        if self.settings_dialog and self.settings_dialog.winfo_exists():
            # ダイアログ側でキャプチャ処理を行い、処理した場合はTrueが返る
            if self.settings_dialog.handle_key_input(key, key_str):
                return True

        # 2. アクション設定フォームのキー入力取得モードの場合
        if self.action_form.is_capturing_key:
            self.after(0, self.action_form.receive_key, key)
            return True # 処理済み
            
        return False # 未処理（コントローラー側でホットキー判定へ）

    def _on_macro_start_ui(self):
        """マクロ開始時のUI更新"""
        print("マクロを開始します...")
        self.title("Auto Clicker Macro (実行中...)")
        self._set_ui_state('disabled')

    def _on_macro_finish_ui(self):
        """マクロ終了時のUI更新"""
        print("GUIをリセットします。")
        self._set_ui_state('normal')
        self.title("Auto Clicker Macro")

    def _add_click_action_by_hotkey(self, x, y, button_type):
        """ホットキーでクリックアクションを直接追加する"""
        try:
            duration = self.action_form.get_duration()
            interval = self.action_form.get_interval()

            action = Action(type='click', duration=duration, interval=interval,
                            x=int(x), y=int(y), button=button_type)
            self._add_action_to_view(action)
        except ValueError:
            print("Could not add action via hotkey: Invalid value in form.")
        except Exception as e:
            print(f"Unexpected error adding action via hotkey: {e}")

    def _update_info_label(self):
        """ホットキーのヒントラベルを現在の設定で更新する"""
        base_hint = "ヒント: 「待機間隔」は、各アクションが実行された後の休憩時間です。"
        hotkey_info = (
            f"開始: {self.settings.start_key.upper()}\n"
            f"停止: {self.settings.stop_key.upper()}\n"
            f"左クリック追加: {self.settings.add_left_key.upper()}\n"
            f"右クリック追加: {self.settings.add_right_key.upper()}"
        )
        info_text = f"{base_hint}\n\n現在のホットキー:\n{hotkey_info}"
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
        if self.settings_dialog and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            return

        def on_save():
            self._update_info_label()

        def on_close():
            self.settings_dialog = None
            self.is_setting_hotkey = False
        
        self.is_setting_hotkey = True
        self.settings_dialog = SettingsDialog(self, self.settings, on_save, on_close)


    # --- UI State Control ---

    def _set_child_widgets_state(self, parent, state):
        """親ウィジェット内のすべての子ウィジェットの状態を再帰的に設定する"""
        for child in parent.winfo_children():
            try:
                # 'state' オプションを持つウィジェットにのみ適用
                child.config(state=state)
            except tk.TclError:
                # 'state' オプションを持たないウィジェット（例: Frame, Label）はスキップ
                pass
            # 子ウィジェットを再帰的に処理
            self._set_child_widgets_state(child, state)

    def _set_ui_state(self, state):
        """マクロ実行中にUIの主要部分を有効/無効にする"""
        # リストボックスの状態を変更 (これで選択、D&D, Deleteキーが無効になる)
        self.listbox.config(state=state)

        # アクションフォーム内の全ウィジェットの状態を変更
        self._set_child_widgets_state(self.action_form, state)

        # メニューバーの主要な項目を無効化
        # '終了' は常に有効にしておく
        self.file_menu.entryconfig("新規作成", state=state)
        self.file_menu.entryconfig("設定を開く", state=state)
        self.file_menu.entryconfig("設定を保存", state=state)
        self.edit_menu.entryconfig("ホットキー設定...", state=state)

        if state == 'disabled':
            self.listbox.unbind("<Button-3>") # 右クリックメニューも無効化
        else:
            self.listbox.bind("<Button-3>", self.show_context_menu) # 再度有効化

if __name__ == "__main__":
    app = AutoClickerApp()
    app.mainloop()
