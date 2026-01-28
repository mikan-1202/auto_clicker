"""
アプリケーションのエントリーポイント
"""
import os
import sys

# プロジェクトルートをsys.pathに追加
# これにより auto_clicker パッケージが見つかるようになります
# このファイル(main.py)の親の親のディレクトリ(プロジェクトルート)をパスに追加します
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from auto_clicker.gui.main_window import AutoClickerApp

if __name__ == "__main__":
    app = AutoClickerApp()
    app.mainloop()
