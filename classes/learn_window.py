# -*- coding: utf-8 -*-
"""旧窗口入口（保留兼容）—— 实际的界面已经换成 `classes/status_window.py`。

2026-09-23 用户要求：「她的状态、记忆、提醒的窗口也要按照剧情模式的风格单独做一个 UI 窗口」。
所以界面重做成了 `StatusWindow`（奶油面板 / 暗红描边 / 金色饰条 / 红色菱形标记，
与剧情模式 engine.css 同一套配色）。这里只留一个别名，避免还有地方 from
classes.learn_window import LearnWindow 时找不到东西。
"""
from classes.status_window import StatusWindow


class LearnWindow(StatusWindow):
    """旧名字，指向新的剧情模式风格窗口（参数/方法保持一致）"""

    def __init__(self, parent=None, on_study=None):
        super().__init__(parent, on_study=on_study)
        self.setWindowTitle("她的状态、记忆与自学")


__all__ = ["LearnWindow", "StatusWindow"]
