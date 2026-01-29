"""
マクロ実行エンジン
"""
import threading
import time
from typing import List, Callable
from .actions import Action

class MacroEngine(threading.Thread):
    """
    アクションリストを別スレッドで順次実行するクラス
    """
    def __init__(self, actions: List[Action], on_finish: Callable = None):
        super().__init__(daemon=True)
        self.actions = actions
        self.on_finish = on_finish
        self._stop_event = threading.Event()

    def run(self):
        """スレッド開始時に呼び出され、アクションを順次実行する"""
        loop_stack = []  # (loop_start_index, remaining_count) を格納するスタック
        i = 0
        try:
            while i < len(self.actions):
                if self._stop_event.is_set():
                    print("マクロがユーザーによって停止されました。")
                    break

                action = self.actions[i]

                if action.type == 'loop_start':
                    # ループ開始: スタックに現在の位置と回数をプッシュ
                    loop_stack.append({'start_index': i, 'count': action.loop_count})
                    i += 1
                    continue

                if action.type == 'loop_end':
                    if not loop_stack:
                        # 対応する loop_start がない
                        print(f"警告: 対応する 'loop_start' がない 'loop_end' をスキップします (index: {i})")
                        i += 1
                        continue

                    current_loop = loop_stack[-1]
                    current_loop['count'] -= 1

                    if current_loop['count'] > 0:
                        # ループを継続: ループの開始点に戻る
                        i = current_loop['start_index'] + 1
                    else:
                        # ループ終了: スタックからポップして次に進む
                        loop_stack.pop()
                        i += 1
                    continue

                # 通常のアクションを実行
                action.execute(self._stop_event)
                if self._stop_event.wait(action.interval):
                    break
                i += 1
        finally:
            print("マクロの実行が終了しました。")
            if self.on_finish:
                # 終了コールバックを呼び出す
                self.on_finish()

    def stop(self):
        """マクロの実行を安全に停止するためのフラグを立てる"""
        self._stop_event.set()