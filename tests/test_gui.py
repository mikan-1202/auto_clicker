"""Tkの画面を生成し、入力を送信せずに編集と読込を検証する。"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from auto_clicker.core.actions import Action
from auto_clicker.core.controller import MacroController
from auto_clicker.core.settings import SettingsManager
from auto_clicker.gui.main_window import AutoClickerApp


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = SettingsManager(self.directory.name)
        with patch.object(MacroController, "start_listener"):
            with patch("auto_clicker.gui.main_window.SettingsManager", return_value=settings):
                self.app = AutoClickerApp()
        self.app.withdraw()
        self.app.update()
        self.addCleanup(self.app.destroy)

    def test_edit_loop_start_does_not_add_pair(self):
        self.app.on_action_add(Action(type="key", key="a"))
        self.app.on_action_add(Action(type="loop_start", loop_count=2))
        self.app.listbox.selection_set(0)
        self.app.load_selected_action_to_form()
        self.app.on_action_add(Action(type="loop_start", loop_count=3))
        self.assertEqual(len(self.app.actions), 3)
        self.assertEqual(self.app.actions[0].loop_count, 3)
        self.assertIsNone(self.app.editing_index)

    def test_failed_load_keeps_settings_and_list(self):
        action = Action(type="key", key="a")
        self.app.on_action_add(action)
        before = self.app.settings.to_dict()
        path = Path(self.directory.name) / "invalid.json"
        path.write_text('{"settings":{"start_key":"f3"},"actions":[{"type":"bad"}]}')
        with patch(
            "auto_clicker.gui.main_window.filedialog.askopenfilename", return_value=str(path)
        ):
            with patch("auto_clicker.gui.main_window.messagebox.showerror") as error:
                self.app.load_preset()
        error.assert_called_once()
        self.assertEqual(self.app.actions, [action])
        self.assertEqual(self.app.settings.to_dict(), before)

    def test_delete_prior_row_cancels_edit(self):
        for key in "ab":
            self.app.on_action_add(Action(type="key", key=key))
        self.app.editing_index = 1
        self.app._delete_action_from_view(0)
        self.assertIsNone(self.app.editing_index)
        self.assertEqual(self.app.actions[0].key, "b")

    def test_disabled_list_cannot_reorder_data(self):
        for key in "ab":
            self.app.on_action_add(Action(type="key", key=key))
        self.app.listbox.drag_data["item_index"] = 0
        self.app._set_ui_state("disabled")
        self.app.listbox.on_drop(SimpleNamespace(y=100))
        self.assertEqual([action.key for action in self.app.actions], ["a", "b"])

    def test_invalid_numeric_entry_is_reported(self):
        self.app.action_form.var_duration.set("invalid")
        with patch("auto_clicker.gui.action_form.messagebox.showerror") as error:
            self.app.action_form._on_add()
        error.assert_called_once()
        self.assertEqual(self.app.actions, [])

    def test_switching_form_cancels_key_capture(self):
        form = self.app.action_form
        form._set_action_type("key")
        form.start_key_capture()
        form._set_action_type("click")
        self.assertFalse(form.is_capturing_key)

    def test_running_macro_blocks_delete(self):
        self.app.on_action_add(Action(type="key", key="a"))
        self.app.listbox.selection_set(0)
        self.app.controller.running = True
        self.app.delete_selected_action()
        self.assertEqual(len(self.app.actions), 1)


if __name__ == "__main__":
    unittest.main()
