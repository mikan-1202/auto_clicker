"""ホットキー設定。壊れたファイルは上書きせず既定値で起動する。"""

from pathlib import Path

from pynput import keyboard

from ..utils import load_json, save_json

DEFAULT_HOTKEYS = {
    "start_key": "f1",
    "stop_key": "f2",
    "add_left_key": "f11",
    "add_right_key": "f12",
}


def valid_key(value):
    return isinstance(value, str) and (len(value) == 1 or value in keyboard.Key.__members__)


def validate_hotkeys(data):
    if not isinstance(data, dict):
        raise ValueError("ホットキー設定はJSONオブジェクトで指定してください。")
    result = DEFAULT_HOTKEYS | data
    if set(result) != set(DEFAULT_HOTKEYS):
        raise ValueError("不明なホットキー設定があります。")
    result = {
        name: value.lower() if isinstance(value, str) else value for name, value in result.items()
    }
    if not all(valid_key(value) for value in result.values()):
        raise ValueError("ホットキーには1文字またはf1、enterなどのキー名を指定してください。")
    if len(set(result.values())) != len(result):
        raise ValueError("ホットキーが重複しています。")
    return result


class SettingsManager:
    CONFIG_FILENAME = "config.json"

    def __init__(self, base_path):
        self.filepath = Path(base_path) / self.CONFIG_FILENAME
        self.load_error = None
        self.apply(DEFAULT_HOTKEYS)
        self.load()

    def to_dict(self):
        return {name: getattr(self, name) for name in DEFAULT_HOTKEYS}

    def apply(self, data):
        validated = validate_hotkeys(data)
        for name, value in validated.items():
            setattr(self, name, value)

    def load(self):
        try:
            self.apply(load_json(self.filepath))
        except FileNotFoundError:
            pass  # 初回は既定値で起動し、設定変更時に保存する。
        except (OSError, ValueError, UnicodeError) as error:
            self.load_error = str(error)

    def save(self, data=None):
        validated = validate_hotkeys(self.to_dict() if data is None else data)
        save_json(self.filepath, validated)
        self.apply(validated)
