# -*- coding: utf-8 -*-
"""「她的记忆与自学」独立窗口。

为什么要单独开窗：自主学习相关的内容（长期记忆、学到的东西、日记）比较长，
放在桌宠对话框里会把她的台词挤掉、也不方便看（用户要求单独一个框显示）。
"""
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout)


class LearnWindow(QDialog):
    """她学到了什么：长期记忆 / 自学笔记 / 日记。

    on_study：点「让她现在学一次」时回调（由桌宠传进来，跑在后台线程里）
    """

    def __init__(self, parent=None, on_study=None):
        super().__init__(parent)
        self.setWindowTitle("她的记忆与自学")
        self.setMinimumSize(520, 420)
        self.resize(600, 480)
        self._on_study = on_study

        lay = QVBoxLayout(self)
        tip = QLabel("下面是她自己记下来的东西：关于你的事、她自学到的内容、还有每天的日记。"
                     "（存在 pets/角色/memory/learned.json）")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.view = QTextEdit(self)
        self.view.setReadOnly(True)
        self.view.setFont(QFont("Microsoft YaHei UI", 10))
        lay.addWidget(self.view, 1)

        # 按钮一律横排（用户要求：不要竖排按钮）
        row = QHBoxLayout()
        self.btn_study = QPushButton("让她现在学一次", self)
        self.btn_refresh = QPushButton("刷新", self)
        self.btn_open = QPushButton("打开记忆文件", self)
        self.btn_close = QPushButton("关闭", self)
        for b in (self.btn_study, self.btn_refresh, self.btn_open, self.btn_close):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_study.clicked.connect(self._study)
        self.btn_open.clicked.connect(self._open_file)
        self.btn_close.clicked.connect(self.close)
        self.refresh()

    def refresh(self):
        try:
            from tool import self_learn as sl
            self.view.setPlainText(sl.summary_text(limit=40))
        except Exception as e:
            self.view.setPlainText("读取失败：%s" % e)

    def _study(self):
        try:
            if self._on_study:
                self._on_study()
                self.view.setPlainText("唔……我去翻两页书，等一下下再点「刷新」。")
        except Exception as e:
            self.view.setPlainText("自习没跑起来：%s" % e)

    def _open_file(self):
        try:
            from tool import self_learn as sl
            p = sl._store_path()
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write('{"notes": [], "diary": {}}')
            os.startfile(p)
        except Exception as e:
            self.view.setPlainText("打不开文件：%s" % e)
