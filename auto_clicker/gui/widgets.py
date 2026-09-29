"""
GUI用のカスタムウィジェット
"""

import math
import tkinter as tk
from tkinter import ttk


class DraggableListbox(tk.Listbox):
    """ドラッグアンドドロップで並べ替え可能なリストボックス"""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_drop)
        self.drag_data = {"item_index": None}
        self.reorder_callback = None  # 並べ替え発生時のコールバック

    def set_reorder_callback(self, callback):
        self.reorder_callback = callback

    def on_click(self, event):
        if self.cget("state") == "disabled" or not self.size():
            self.drag_data["item_index"] = None
            return
        # ドラッグ開始位置のインデックスを取得
        index = self.nearest(event.y)
        if index >= 0:
            self.drag_data["item_index"] = index

    def on_drag(self, event):
        if self.cget("state") == "disabled" or self.drag_data["item_index"] is None:
            return
        # ドラッグ中の視覚効果（カーソル位置の項目を選択状態にする）
        new_index = self.nearest(event.y)
        if new_index != self.drag_data["item_index"]:
            # 実際の移動はドロップ時に行うが、見た目上で選択位置を変える
            self.selection_clear(0, tk.END)
            self.selection_set(new_index)

    def on_drop(self, event):
        if self.cget("state") == "disabled":
            self.drag_data["item_index"] = None
            return
        # ドロップ時の処理
        new_index = self.nearest(event.y)
        old_index = self.drag_data["item_index"]

        if old_index is not None and new_index != old_index:
            # リストボックスの項目を入れ替え
            text = self.get(old_index)
            self.delete(old_index)
            self.insert(new_index, text)
            self.selection_clear(0, tk.END)
            self.selection_set(new_index)

            # データ側の同期用コールバックを実行
            if self.reorder_callback:
                self.reorder_callback(old_index, new_index)

        self.drag_data["item_index"] = None


class CustomScale(tk.Canvas):
    """
    Canvasを使用したカスタムスライダー。
    丸いハンドルと、0.1/0.5刻みの目盛りを持つ。
    """

    def __init__(self, parent, variable, from_=0.0, to=5.0, command=None, **kwargs):
        # 親フレームの背景色を取得してCanvasの背景に設定（馴染ませるため）
        bg_color = ttk.Style().lookup("TFrame", "background")
        super().__init__(parent, bg=bg_color, highlightthickness=0, height=30, **kwargs)

        self.variable = variable
        self.from_ = from_
        self.to = to
        self.command = command

        # 変数の変更を監視して再描画
        self.variable.trace_add("write", self._update_view)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)

        self._width = 1

    def _on_resize(self, event):
        self._width = event.width
        self._draw()

    def _val_to_x(self, val):
        margin = 10
        w = self._width - 2 * margin
        if w <= 0:
            return margin
        ratio = (val - self.from_) / (self.to - self.from_)
        return margin + ratio * w

    def _x_to_val(self, x):
        margin = 10
        w = self._width - 2 * margin
        if w <= 0:
            return self.from_
        ratio = (x - margin) / w
        val = self.from_ + ratio * (self.to - self.from_)
        return max(self.from_, min(self.to, val))

    def _draw(self):
        self.delete("all")
        w = self._width
        cy = 12  # スライダーの中心Y座標
        margin = 10

        # 1. 軸線 (Trough)
        self.create_line(margin, cy, w - margin, cy, fill="#a0a0a0", width=2, capstyle="round")

        # 2. 目盛り (Ticks)
        tick_y = cy + 6
        val_range = self.to - self.from_
        if val_range > 0:
            steps = int(val_range / 0.1 + 0.0001)
            for i in range(steps + 1):
                val = self.from_ + i * 0.1
                x = self._val_to_x(val)

                # 0.5刻みかどうか判定
                rem = val % 0.5
                is_long = rem < 0.001 or rem > 0.499

                h = 7 if is_long else 3
                color = "#606060" if is_long else "#a0a0a0"
                self.create_line(x, tick_y, x, tick_y + h, fill=color)

        # 3. ハンドル (Circle)
        try:
            current_val = self.variable.get()
        except tk.TclError:
            current_val = self.from_

        if not math.isfinite(current_val):
            current_val = self.from_
        cx = self._val_to_x(current_val)
        r = 7
        # 白い円にグレーの枠線
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill="white", outline="#606060", width=1)

    def _update_view(self, *args):
        self._draw()

    def _update_val(self, x):
        if self.cget("state") == "disabled":
            return
        val = self._x_to_val(x)
        rounded_val = round(val, 1)
        self.variable.set(rounded_val)
        if self.command:
            self.command(str(rounded_val))

    def _on_click(self, event):
        self._update_val(event.x)

    def _on_drag(self, event):
        self._update_val(event.x)
