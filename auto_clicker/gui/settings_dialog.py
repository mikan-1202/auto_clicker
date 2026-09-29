"""
ホットキー設定ダイアログ
"""
import tkinter as tk
from tkinter import ttk, messagebox

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, settings, on_save_callback, on_close_callback):
        super().__init__(parent)
        self.settings = settings
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback
        self.capturing_button = None
        
        self.title("ホットキー設定")
        self.geometry("350x200")
        self.resizable(False, False)
        self.transient(parent) # 親ウィンドウの前面に表示
        self.grab_set() # モーダル化（他のウィンドウ操作をブロック）
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._init_ui()

    def _init_ui(self):
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill="both", expand=True)

        labels = ["マクロ開始:", "マクロ停止:", "左クリック追加:", "右クリック追加:"]
        current_keys = [
            self.settings.start_key, self.settings.stop_key,
            self.settings.add_left_key, self.settings.add_right_key
        ]
        self.buttons = []

        for i, text in enumerate(labels):
            ttk.Label(frame, text=text).grid(row=i, column=0, sticky="w", pady=5, padx=5)
            button = ttk.Button(frame, text=current_keys[i].upper(), width=20)
            button.config(command=lambda b=button: self._start_capture(b))
            button.grid(row=i, column=1, sticky="ew", pady=5, padx=5)
            self.buttons.append(button)

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(labels), column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="OK", command=self._apply_and_close).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="キャンセル", command=self._on_close).pack(side="left", padx=10)

    def _start_capture(self, button):
        if self.capturing_button:
            messagebox.showinfo("情報", "キー入力待機中です。いずれかのキーを押してください。", parent=self)
            return
        self.capturing_button = button
        button.config(text="キーを押してください...")

    def handle_key_input(self, key, key_str):
        """
        外部（メインウィンドウ）からキー入力を受け取る。
        キャプチャ中であれば処理してTrueを返す。
        """
        if self.capturing_button and key_str:
            # キー重複チェックなどは保存時にまとめて行うか、ここで行う
            self.capturing_button.config(text=key_str.upper())
            self.capturing_button = None
            return True
        return False

    def _apply_and_close(self):
        if self.capturing_button:
            messagebox.showerror("エラー", "キー入力待機中の項目があります。\nいずれかのキーを押して設定を完了してください。", parent=self)
            return

        new_keys = [b.cget("text").lower() for b in self.buttons]
        
        # 重複チェック
        if len(set(k.lower() for k in new_keys)) != len(new_keys):
            messagebox.showerror("エラー", "ホットキーが重複しています。", parent=self)
            return
        
        # 設定を保存
        self.settings.start_key = new_keys[0]
        self.settings.stop_key = new_keys[1]
        self.settings.add_left_key = new_keys[2]
        self.settings.add_right_key = new_keys[3]
        
        self.settings.save()
        
        if self.on_save_callback:
            self.on_save_callback()
            
        messagebox.showinfo("設定", "ホットキーを更新しました。", parent=self)
        self._on_close()

    def _on_close(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()
