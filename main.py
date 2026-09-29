"""
Application entry point.
"""
import os
import ctypes
from auto_clicker.gui.main_window import AutoClickerApp

if __name__ == "__main__":
    # Windowsのタスクバーに独自のアイコンを表示させるための設定
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("myproject.autoclicker.v1")
    except Exception:
        pass

    app = AutoClickerApp()

    # アイコンの設定 (main.pyと同じ場所に icon.ico がある場合)
    icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    if os.path.exists(icon_path):
        app.iconbitmap(icon_path)

    app.mainloop()