"""既存のsettings/actions形式を維持したプリセットの検証・入出力。"""

from dataclasses import asdict

from ..utils import load_json, save_json
from .actions import Action
from .settings import validate_hotkeys


def validate_actions(actions, hotkeys):
    depth = 0
    reserved_keys = {key.lower() for key in hotkeys.values()}
    for index, action in enumerate(actions, 1):
        action.validate()
        if action.type == "loop_start":
            depth += 1
        elif action.type == "loop_end":
            depth -= 1
            if depth < 0:
                raise ValueError(f"{index}行目のループ終了に対応する開始がありません。")
        elif action.type == "key" and action.key.lower() in reserved_keys:
            raise ValueError(f"{index}行目のキー入力がホットキーと重複しています。")
    if depth:
        raise ValueError("ループ開始と終了の数が一致しません。")


def load_preset(filepath):
    data = load_json(filepath)
    if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
        raise ValueError("プリセットにはactions配列が必要です。")
    settings = validate_hotkeys(data.get("settings", {}))
    try:
        actions = [Action(**item) for item in data["actions"]]
    except TypeError as error:
        raise ValueError("アクションの項目または形式が不正です。") from error
    validate_actions(actions, settings)
    return settings, actions


def save_preset(filepath, settings, actions):
    settings = validate_hotkeys(settings)
    validate_actions(actions, settings)
    save_json(filepath, {"settings": settings, "actions": [asdict(a) for a in actions]})
