"""
汎用ユーティリティ関数
"""
import json
import os
from pynput import keyboard

# --- File I/O ---

def save_json(filepath: str, data: dict):
    """データをJSONファイルに保存する"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_json(filepath: str) -> dict:
    """JSONファイルからデータを読み込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Input Utils ---

def get_key_str(key) -> str | None:
    """pynputのキーイベントオブジェクトを正規化された文字列に変換する"""
    if isinstance(key, keyboard.Key):
        return key.name
    elif isinstance(key, keyboard.KeyCode) and key.char:
        return key.char
    return None