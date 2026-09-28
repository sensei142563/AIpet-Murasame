# -*- coding: utf-8 -*-
"""「她的状态」窗口：把 tool/status_snapshot.py 收好的那一页画出来。

分工
----
* tool/status_snapshot.py —— 纯数据（9 个内心模块的现状），可离线验证
* 本文件 —— 只负责画：一页一个标签页，一张卡一个分组框
这样"显示的内容对不对"能用不开 GUI 的方式验证，窗口本身也简单到不容易出岔子。

打开方式：桌宠右键菜单「🪟 她的状态」，或 `python -m classes.status_window`（调试用）
"""
import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QDialog, QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout,
                             QWidget)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tool import status_snapshot as SS

# 标签色（数据层只给样式名，颜色在这里定）
_TAG_COLORS = {
    SS.TAG_RED: "#c2564f",
    SS.TAG_GOLD: "#b8873f",
    SS.TAG_PLAIN: "#7a7a7a",
}
_CARD_QSS = """
QGroupBox { border: 1px solid #d8d2c6; border-radius: 6px; margin-top: 12px;
            padding: 8px 8px 6px 8px; background: #fbf9f5; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #6b5a3e; }
QLabel#statusBody { color: #33322e; }
QLabel#statusSub  { color: #8a8172; }
"""


def _tag_label(text: str, style: str = SS.TAG_PLAIN) -> QLabel:
    lb = QLabel(str(text))
    lb.setObjectName("statusTag")
    lb.setStyleSheet("color: %s; border: 1px solid %s; border-radius: 8px;"
                     "padding: 1px 7px;" % (_TAG_COLORS.get(style, "#7a7a7a"),
                                            _TAG_COLORS.get(style, "#7a7a7a")))
    f = QFont()
    f.setPointSize(9)
    lb.setFont(f)
    return lb


def _card_widget(card: dict) -> QWidget:
    """一张卡：标题 + 彩色标签 + 正文（出错时整张卡偏红，一眼能看出哪项坏了）"""
    box = QGroupBox(str(card.get("title") or ""))
    box.setObjectName("statusCardError" if card.get("error") else "statusCard")
    if card.get("error"):
        box.setStyleSheet("QGroupBox { border: 1px solid #c2564f; }")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(4)

    tags = card.get("tags") or []
    if tags:
        row = QHBoxLayout()
        row.setSpacing(6)
        for t in tags:
            try:
                txt, style = t[0], (t[1] if len(t) > 1 else SS.TAG_PLAIN)
            except Exception:
                txt, style = str(t), SS.TAG_PLAIN
            row.addWidget(_tag_label(txt, style))
        row.addStretch(1)
        lay.addLayout(row)

    body = QLabel(str(card.get("body") or ""))
    body.setObjectName("statusBody")
    body.setWordWrap(True)
    body.setTextInteractionFlags(Qt.TextSelectableByMouse)
    body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    lay.addWidget(body)
    return box


class StatusWindow(QDialog):
    """一页看完她此刻的状态（数据取自 tool.status_snapshot）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusWindow")
        self.setWindowTitle("她的状态")
        self.setMinimumSize(520, 420)
        self.resize(640, 620)
        self.setStyleSheet(_CARD_QSS)
        self._snap = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        head = QHBoxLayout()
        self.lb_title = QLabel("她的状态")
        self.lb_title.setObjectName("statusTitle")
        tf = QFont()
        tf.setPointSize(12)
        tf.setBold(True)
        self.lb_title.setFont(tf)
        head.addWidget(self.lb_title)
        head.addStretch(1)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setObjectName("statusRefresh")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_copy = QPushButton("复制全部")
        self.btn_copy.setObjectName("statusCopy")
        self.btn_copy.clicked.connect(self.copy_all)
        self.btn_dir = QPushButton("打开数据目录")
        self.btn_dir.setObjectName("statusOpenDir")
        self.btn_dir.clicked.connect(self.open_data_dir)
        self.btn_close = QPushButton("关闭")
        self.btn_close.setObjectName("statusClose")
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_refresh, self.btn_copy, self.btn_dir, self.btn_close):
            head.addWidget(b)
        outer.addLayout(head)

        self.lb_sub = QLabel("")
        self.lb_sub.setObjectName("statusSub")
        self.lb_sub.setWordWrap(True)
        outer.addWidget(self.lb_sub)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #ded8cc;")
        outer.addWidget(line)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("statusTabs")
        outer.addWidget(self.tabs, 1)

        self.refresh()

    # ── 数据 → 界面 ────────────────────────────────────
    def refresh(self):
        """重新采集并铺卡片（任一页取不到也照常显示，坏的那张卡会标红）"""
        self._snap = SS.snapshot()
        self.lb_sub.setText(str(self._snap.get("subtitle") or ""))
        keep = self.tabs.currentIndex()
        self.tabs.clear()
        for page in self._snap.get("pages") or []:
            area = QScrollArea()
            area.setWidgetResizable(True)
            holder = QWidget()
            v = QVBoxLayout(holder)
            v.setContentsMargins(6, 6, 6, 6)
            v.setSpacing(8)
            for card in page.get("cards") or []:
                v.addWidget(_card_widget(card))
            v.addStretch(1)
            area.setWidget(holder)
            self.tabs.addTab(area, str(page.get("title") or ""))
        if 0 <= keep < self.tabs.count():
            self.tabs.setCurrentIndex(keep)

    # ── 给主人/自检用的读数 ────────────────────────────
    def page_titles(self) -> list:
        return [self.tabs.tabText(i) for i in range(self.tabs.count())]

    def card_count(self) -> int:
        n = 0
        for page in self._snap.get("pages") or []:
            n += len(page.get("cards") or [])
        return n

    def error_titles(self) -> list:
        """哪些卡是"取不到"的（自检/排查时一眼看出断在哪一环）"""
        out = []
        for page in self._snap.get("pages") or []:
            for c in page.get("cards") or []:
                if c.get("error"):
                    out.append(str(c.get("title")))
        return out

    def snapshot_text(self) -> str:
        return SS.as_text(self._snap)

    # ── 按钮 ───────────────────────────────────────────
    def copy_all(self) -> bool:
        """把整页复制成纯文字（贴给别人/报 bug 最方便）"""
        try:
            QApplication.clipboard().setText(self.snapshot_text())
            self.btn_copy.setText("已复制")
            return True
        except Exception as e:
            print("[状态窗] ⚠ 复制失败: %s" % e)
            return False

    def open_data_dir(self) -> bool:
        """打开她的数据目录（内存文件都在里面，出问题时可以自己看）"""
        d = SS.data_dir()
        try:
            os.makedirs(d, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(d)          # Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
            return True
        except Exception as e:
            print("[状态窗] ⚠ 打开目录失败（%s）：%s" % (d, e))
            return False


_WIN = None


def show_status_window(parent=None) -> "StatusWindow":
    """打开（已开着就刷新并提到前面）。桌宠右键菜单走这里。"""
    global _WIN
    try:
        if _WIN is not None:
            _WIN.refresh()
            _WIN.show()
            _WIN.raise_()
            _WIN.activateWindow()
            return _WIN
    except Exception:
        _WIN = None
    _WIN = StatusWindow(parent)
    _WIN.show()
    return _WIN


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = StatusWindow()
    w.show()
    sys.exit(app.exec_())
