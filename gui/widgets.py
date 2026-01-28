"""
GUI用のカスタムウィジェット
"""
import tkinter as tk
from tkinter import ttk

class DraggableListbox(tk.Listbox):
    """ドラッグアンドドロップで並べ替え可能なリストボックス"""
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.on_drag)
        self.bind('<ButtonRelease-1>', self.on_drop)
        self.drag_data = {"item_index": None}
        self.reorder_callback = None # 並べ替え発生時のコールバック

    def set_reorder_callback(self, callback):
        self.reorder_callback = callback

    def on_click(self, event):
        # ドラッグ開始位置のインデックスを取得
        index = self.nearest(event.y)
        if index >= 0:
            self.drag_data["item_index"] = index

    def on_drag(self, event):
        # ドラッグ中の視覚効果（カーソル位置の項目を選択状態にする）
        new_index = self.nearest(event.y)
        if new_index != self.drag_data["item_index"]:
            # 実際の移動はドロップ時に行うが、見た目上で選択位置を変える
            self.selection_clear(0, tk.END)
            self.selection_set(new_index)

    def on_drop(self, event):
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
