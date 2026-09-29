import os
import json
from ..utils import load_json, save_json

class SettingsManager:
    """
    アプリケーションの設定を管理するクラス。
    設定ファイルが存在しない場合は、デフォルト値で自動的に作成する。
    """
    DEFAULT_START_KEY = "f1"
    DEFAULT_STOP_KEY = "f2"
    DEFAULT_ADD_LEFT_KEY = "f11"
    DEFAULT_ADD_RIGHT_KEY = "f12"
    CONFIG_FILENAME = "config.json"

    def __init__(self, base_path: str):
        """base_path: 設定ファイルを保存するディレクトリのパス"""
        self.filepath = os.path.join(base_path, self.CONFIG_FILENAME)

        # デフォルト値をインスタンス変数に設定
        self.start_key = self.DEFAULT_START_KEY
        self.stop_key = self.DEFAULT_STOP_KEY
        self.add_left_key = self.DEFAULT_ADD_LEFT_KEY
        self.add_right_key = self.DEFAULT_ADD_RIGHT_KEY
        
        # 設定ファイルを読み込む（存在しない場合は作成される）
        self.load()

    def load(self):
        """設定ファイルから読み込む。ファイルが存在しないか不正な場合は、デフォルト設定で新規作成する。"""
        try:
            data = load_json(self.filepath)
            self.start_key = data.get("start_key", self.start_key)
            self.stop_key = data.get("stop_key", self.stop_key)
            self.add_left_key = data.get("add_left_key", self.add_left_key)
            self.add_right_key = data.get("add_right_key", self.add_right_key)
        except (FileNotFoundError, json.JSONDecodeError):
            # ファイルが存在しない、またはJSONとして不正な場合、現在の設定でファイルを保存する
            self.save()

    def save(self):
        """設定ファイルに保存する"""
        settings_data = {
            "start_key": self.start_key,
            "stop_key": self.stop_key,
            "add_left_key": self.add_left_key,
            "add_right_key": self.add_right_key
        }
        save_json(self.filepath, settings_data)