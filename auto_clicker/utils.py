"""JSON入出力とキー表現の変換。"""

import json
import os
import tempfile
from pathlib import Path

from pynput import keyboard


def save_json(filepath, data):
    """同じディレクトリの一時ファイルから置換し、書込失敗時に元を保つ。"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=4, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_json(filepath):
    with open(filepath, encoding="utf-8") as stream:
        return json.load(stream)


def get_key_str(key):
    if isinstance(key, keyboard.Key):
        return key.name
    if isinstance(key, keyboard.KeyCode) and key.char:
        return key.char
    return None
