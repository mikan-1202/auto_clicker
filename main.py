"""アプリケーションのエントリーポイント。"""

import ctypes
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from auto_clicker.gui.main_window import AutoClickerApp


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "myproject.autoclicker.v1"
            )
        except OSError:
            logging.warning("WindowsのアプリIDを設定できませんでした。", exc_info=True)
    try:
        app = AutoClickerApp()
    except (OSError, RuntimeError, tk.TclError) as error:
        messagebox.showerror("起動エラー", f"起動できませんでした。\n{error}")
        return 1
    icon_path = Path(__file__).resolve().with_name("icon.ico")
    if icon_path.exists():
        try:
            app.iconbitmap(str(icon_path))
        except tk.TclError:
            logging.warning("アイコンを読み込めませんでした。", exc_info=True)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
