"""実入力をモック化し、実行順序・停止・JSON互換性を検証する。"""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pynput import keyboard

from auto_clicker.core.actions import Action
from auto_clicker.core.controller import MacroController
from auto_clicker.core.engine import MacroEngine
from auto_clicker.core.presets import load_preset, save_preset, validate_actions
from auto_clicker.core.settings import DEFAULT_HOTKEYS, SettingsManager, validate_hotkeys
from auto_clicker.utils import save_json


class ActionTests(unittest.TestCase):
    def test_invalid_action_values(self):
        cases = [
            {"type": "unknown"},
            {"type": "key", "key": "not-a-key"},
            {"type": "key", "key": "a", "duration": -1},
            {"type": "key", "key": "a", "interval": float("nan")},
            {"type": "key", "key": "a", "duration": float("inf")},
            {"type": "key", "key": "a", "duration": True},
            {"type": "key", "key": "a", "duration": 10**400},
            {"type": "click", "x": 1.5, "y": 0},
            {"type": "click", "x": 0, "y": 0, "button": "unknown"},
            {"type": "loop_start", "loop_count": 0},
            {"type": "loop_start", "loop_count": True},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                Action(**case)

    def test_negative_monitor_coordinates_are_allowed(self):
        Action(type="click", x=-1920, y=-100)

    def test_key_is_released_when_wait_fails(self):
        controller = Mock()
        with patch("auto_clicker.core.actions.get_keyboard_controller", return_value=controller):
            with patch("auto_clicker.core.actions.wait", side_effect=RuntimeError("wait")):
                with self.assertRaises(RuntimeError):
                    Action(type="key", key="a", duration=1).execute()
        controller.press.assert_called_once_with("a")
        controller.release.assert_called_once_with("a")

    def test_mouse_is_released_when_hold_fails(self):
        controller = Mock()
        with patch("auto_clicker.core.actions.get_mouse_controller", return_value=controller):
            with patch("auto_clicker.core.actions.wait", side_effect=[False, RuntimeError("wait")]):
                with self.assertRaises(RuntimeError):
                    Action(type="click", x=0, y=0, duration=1).execute()
        controller.release.assert_called_once()

    def test_stop_during_cursor_settle_does_not_click(self):
        controller = Mock()
        with patch("auto_clicker.core.actions.get_mouse_controller", return_value=controller):
            with patch("auto_clicker.core.actions.wait", return_value=True):
                Action(type="click", x=0, y=0).execute()
        controller.click.assert_not_called()
        controller.press.assert_not_called()

    def test_stopped_action_does_not_access_device(self):
        stop = threading.Event()
        stop.set()
        with patch("auto_clicker.core.actions.get_keyboard_controller") as controller:
            Action(type="key", key="a").execute(stop)
        controller.assert_not_called()


class EngineTests(unittest.TestCase):
    def test_nested_loop_preserves_order(self):
        actions = [
            Action(type="loop_start", loop_count=2),
            Action(type="key", key="a", interval=0),
            Action(type="loop_start", loop_count=3),
            Action(type="key", key="b", interval=0),
            Action(type="loop_end"),
            Action(type="loop_end"),
        ]
        keys = []
        with patch.object(Action, "execute", lambda action, stop: keys.append(action.key)):
            engine = MacroEngine(actions)
            engine.run()
        self.assertIsNone(engine.error)
        self.assertEqual(keys, list("abbbabbb"))

    def test_stop_interrupts_long_interval(self):
        executed = threading.Event()
        finished = Mock()
        engine = MacroEngine([Action(type="key", key="a", interval=60)], finished)
        with patch.object(Action, "execute", side_effect=lambda stop: executed.set()):
            engine.start()
            try:
                self.assertTrue(executed.wait(2))
                engine.stop()
                engine.join(2)
                self.assertFalse(engine.is_alive())
            finally:
                engine.stop()
                engine.join(2)
        finished.assert_called_once()

    def test_execution_error_still_finishes(self):
        finished = Mock()
        engine = MacroEngine([Action(type="key", key="a")], finished)
        with patch.object(Action, "execute", side_effect=OSError("device")):
            engine.run()
        self.assertIsInstance(engine.error, OSError)
        finished.assert_called_once()


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "preset.json"

    def test_legacy_schema_round_trip(self):
        actions = [Action(type="click", x=-10, y=20), Action(type="key", key="enter")]
        save_preset(self.path, DEFAULT_HOTKEYS, actions)
        settings, restored = load_preset(self.path)
        self.assertEqual(settings, DEFAULT_HOTKEYS)
        self.assertEqual(restored, actions)

    def test_invalid_preset_structure(self):
        for value in [[], {}, {"actions": {}}, {"actions": [None]}, {"actions": [{"type": "bad"}]}]:
            with self.subTest(value=value):
                self.path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_preset(self.path)

    def test_unbalanced_loops_and_reserved_keys(self):
        cases = [
            [Action(type="loop_start")],
            [Action(type="loop_end")],
            [Action(type="key", key="f2")],
        ]
        for actions in cases:
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                validate_actions(actions, DEFAULT_HOTKEYS)

    def test_atomic_save_preserves_original_on_replace_failure(self):
        self.path.write_text("original", encoding="utf-8")
        with patch("auto_clicker.utils.os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                save_json(self.path, {"new": True})
        self.assertEqual(self.path.read_text(encoding="utf-8"), "original")
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_corrupt_settings_are_not_overwritten(self):
        path = self.path.parent / "config.json"
        path.write_text("broken", encoding="utf-8")
        settings = SettingsManager(path.parent)
        self.assertEqual(settings.to_dict(), DEFAULT_HOTKEYS)
        self.assertIsNotNone(settings.load_error)
        self.assertEqual(path.read_text(encoding="utf-8"), "broken")

    def test_settings_failure_does_not_change_live_keys(self):
        settings = SettingsManager(self.path.parent)
        with patch("auto_clicker.core.settings.save_json", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                settings.save(DEFAULT_HOTKEYS | {"start_key": "f3"})
        self.assertEqual(settings.to_dict(), DEFAULT_HOTKEYS)

    def test_hotkey_validation(self):
        self.assertEqual(validate_hotkeys({"start_key": "F1"}), DEFAULT_HOTKEYS)
        for value in [[], {"start_key": None}, {"start_key": "f2"}, {"extra": "a"}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_hotkeys(value)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.actions = [Action(type="key", key="a", interval=0)]
        self.finished = Mock()
        self.errors = Mock()
        self.controller = MacroController(
            SettingsManager(directory.name),
            lambda: self.actions,
            {"on_finish": self.finished, "on_error": self.errors},
        )

    def finish(self):
        engine = self.controller.macro_engine
        self.assertIsNotNone(engine)
        engine.join(2)
        self.assertFalse(engine.is_alive())
        self.controller.process_pending()

    def test_natural_finish_allows_second_run(self):
        with patch.object(Action, "execute") as execute:
            for _ in range(2):
                self.controller.start_macro()
                self.finish()
                self.assertFalse(self.controller.running)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(self.finished.call_count, 2)

    def test_stop_blocks_restart_until_thread_finishes(self):
        entered = threading.Event()
        release = threading.Event()

        def execute(action, stop):
            entered.set()
            release.wait(2)

        with patch.object(Action, "execute", execute):
            self.controller.start_macro()
            engine = self.controller.macro_engine
            try:
                self.assertTrue(entered.wait(2))
                self.controller.stop_macro()
                self.controller.start_macro()
                self.assertIs(self.controller.macro_engine, engine)
                self.assertTrue(self.controller.running)
            finally:
                release.set()
                self.finish()
        self.assertFalse(self.controller.running)

    def test_snapshot_is_independent_of_editor_list(self):
        with patch.object(MacroEngine, "start"):
            self.controller.start_macro()
        self.actions[0].key = "b"
        self.actions.clear()
        self.assertEqual(self.controller.macro_engine.actions[0].key, "a")

    def test_listener_only_queues_and_debounces(self):
        received = Mock()
        self.controller.callbacks["on_raw_key"] = received
        key = keyboard.KeyCode.from_char("a")
        self.controller._on_key_press(key)
        self.controller._on_key_press(key)
        received.assert_not_called()
        self.controller.process_pending()
        received.assert_called_once()
        self.controller._on_key_release(key)
        self.controller._on_key_press(key)
        self.controller.process_pending()
        self.assertEqual(received.call_count, 2)

    def test_engine_error_is_reported_after_finish(self):
        with patch.object(Action, "execute", side_effect=OSError("device")):
            self.controller.start_macro()
            self.finish()
        self.assertFalse(self.controller.running)
        self.errors.assert_called_once()

    def test_invalid_macro_is_rejected_before_start(self):
        self.actions[:] = [Action(type="loop_start")]
        self.controller.start_macro()
        self.assertIsNone(self.controller.macro_engine)
        self.errors.assert_called_once()


if __name__ == "__main__":
    unittest.main()
