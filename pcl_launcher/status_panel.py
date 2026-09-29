# -*- coding: utf-8 -*-
"""启动器「状态」页：把 tool/status_snapshot.py 收好的那一页画出来。

为什么要有这一页
----------------
V1.18 给桌宠加了九个"内心"模块（心情好感 / 习惯 / 开口时机 / 动机 / 关怀 / 提醒 /
任务经验 / 自主分档 / 自主学习）以及插件、联网搜索等开关。它们原来**只挂在桌宠的右键
菜单**上，从启动器进来的人找不到（用户实测："本次更新的东西有做到前端吗？我找不到"）。
这一页把同一份数据画出来，并且把**这次新增的开关**列在最上面：现在是开是关一眼看到、
也知道要去哪儿改。

分工：数据全来自 `tool/status_snapshot.py`（纯 dict、可离线验证），这一层只负责画。
外壳会自动对本页做透明化，并在本页 `_reload()` 之后重新透明化（见 silicon_window
的 `_hook_repaint_transparency`），所以刷新方法就叫 `_reload`。
"""
import os
import subprocess
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QSizePolicy, QTabWidget,
                             QVBoxLayout, QWidget)

from .colors import accent_text, ok_text, warn_text

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _switches() -> list:
    """这次新增的开关现状 → [(名字, 值(bool 或 str), 去哪儿改)]

    ⚠ 全部走各自的模块函数（它们才是唯一真相），别在这里另读 config.json：
      开关的默认值、以及"配置缺失时怎么办"的规则都在模块里。
    """
    out = []

    def _add(name, fn, where="桌宠右键菜单"):
        try:
            out.append((name, fn(), where))
        except Exception as e:
            out.append((name, "取不到（%s）" % type(e).__name__, where))

    try:
        from tool import plugins as _pl
        _add("插件系统（你装的插件能不能用）", _pl.enabled)
    except Exception:
        pass
    try:
        from tool import web_search as _ws
        _add("联网搜索（不确定就上网查）", _ws.enabled)
    except Exception:
        pass
    try:
        from tool import self_learn as _sl
        _add("自主学习（她自己记东西）", _sl.enabled)
    except Exception:
        pass
    try:
        from tool import care as _care
        _add("主动关怀（熬夜/久坐/陪伴天数）", _care.enabled)
    except Exception:
        pass
    try:
        from tool import reminder as _rm
        _add("提醒与待办（你交代的事一定叫你）", _rm.enabled)
    except Exception:
        pass
    try:
        from tool import habits as _hb
        _add("习惯采集（作息/常用软件，只记计数）", _hb.enabled)
    except Exception:
        pass
    try:
        from tool import attention as _at
        _add("开口时机打分（防话痨）", _at.enabled)
    except Exception:
        pass
    try:
        from tool import autonomy as _au
        _add("自主行动分档", _au.level_label, "桌宠右键「自主性」")
    except Exception:
        pass
    try:
        from longtext.model_config import get_vision_model_config
        v = get_vision_model_config()
        out.append(("识图用的模型", (v or {}).get("model") or "**没配 Key**（识图会失败）",
                    "启动器「设置」页"))
    except Exception:
        pass
    return out


class PCLStatusPanel(QWidget):
    """她的状态：九个内心模块的现状 + 本次新增开关一览"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snap = {}
        self._build()
        self._reload()

    # ── 搭骨架（只做一次；刷新只重铺内容）────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("她的状态")
        tf = QFont()
        tf.setPointSize(15)
        tf.setBold(True)
        title.setFont(tf)
        head.addWidget(title)
        self.lb_sub = QLabel("")
        self.lb_sub.setWordWrap(True)
        self.lb_sub.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        head.addWidget(self.lb_sub, 1)
        for text, slot, name in (("刷新", self._reload, "statusRefresh"),
                                 ("复制全部", self.copy_all, "statusCopy"),
                                 ("打开数据目录", self.open_data_dir, "statusOpenDir")):
            b = QPushButton(text)
            b.setObjectName(name)
            b.clicked.connect(slot)
            head.addWidget(b)
        root.addLayout(head)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        root.addWidget(line)

        # 开关一览：放在最上面 —— 这正是"本次更新的东西在哪儿"的答案
        self.box_sw = QGroupBox("这次新增的开关（在桌宠右键菜单里改；识图在「设置」页）")
        self.box_sw.setObjectName("statusSwitches")
        self.lay_sw = QVBoxLayout(self.box_sw)
        self.lay_sw.setContentsMargins(10, 6, 10, 8)
        self.lay_sw.setSpacing(3)
        root.addWidget(self.box_sw)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("statusTabs")
        root.addWidget(self.tabs, 1)

    # ── 数据 → 界面 ────────────────────────────────────
    def _reload(self):
        """重新采集并铺内容（任一页取不到也照常显示，坏的那张卡标红）"""
        try:
            from tool import status_snapshot as SS
            self._snap = SS.snapshot()
        except Exception as e:
            self._snap = {"subtitle": "取不到状态数据：%s: %s" % (type(e).__name__, e),
                          "generated_at": "", "pages": []}

        self.lb_sub.setText("%s（%s 采集）" % (self._snap.get("subtitle") or "",
                                              self._snap.get("generated_at") or "刚刚"))
        self._fill_switches()
        keep = self.tabs.currentIndex()
        self.tabs.clear()
        for page in self._snap.get("pages") or []:
            area = QScrollArea()
            area.setWidgetResizable(True)
            holder = QWidget()
            v = QVBoxLayout(holder)
            v.setContentsMargins(4, 4, 4, 4)
            v.setSpacing(8)
            # ⚠ 页级标签（心情 62·不错 / 关系 20.0 / 在一起第 N 天 / 活跃度）也要画出来：
            #   它们本来只出现在副标题那一行里，等于"一眼要看到的数"被藏起来了。
            if page.get("tags"):
                v.addWidget(self._tag_row(page["tags"]))
            for card in page.get("cards") or []:
                v.addWidget(self._card(card))
            v.addStretch(1)
            area.setWidget(holder)
            self.tabs.addTab(area, str(page.get("title") or ""))
        if 0 <= keep < self.tabs.count():
            self.tabs.setCurrentIndex(keep)

    def _tag_row(self, tags) -> QWidget:
        """一排彩色小标签（页级那些数）"""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(2, 2, 2, 0)
        row.setSpacing(8)
        for t in tags:
            txt = t[0] if isinstance(t, (list, tuple)) else t
            style = (t[1] if isinstance(t, (list, tuple)) and len(t) > 1 else "")
            lb = QLabel(str(txt))
            lb.setObjectName("statusTag")
            color = warn_text().name() if style == "red" else accent_text().name()
            lb.setStyleSheet("color: %s; font-size: 12px;" % color)
            row.addWidget(lb)
        row.addStretch(1)
        return box

    def _fill_switches(self):
        while self.lay_sw.count():
            it = self.lay_sw.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        for name, val, where in _switches():
            lb = QLabel()
            lb.setObjectName("statusSwitch")
            lb.setWordWrap(True)
            if isinstance(val, bool):
                mark = "✅ 开" if val else "⭕ 关"
                color = ok_text().name() if val else warn_text().name()
            else:
                mark = str(val)
                color = accent_text().name()
            lb.setText("%s　<b>%s</b>　<span style='font-size:11px'>（%s）</span>"
                       % (mark, name, where))
            lb.setStyleSheet("color: %s;" % color)
            self.lay_sw.addWidget(lb)

    def _card(self, card: dict) -> QWidget:
        err = bool(card.get("error"))
        box = QGroupBox(str(card.get("title") or ""))
        box.setObjectName("statusCardError" if err else "statusCard")
        if err:
            # 不给写死底色（浅色主题会变"浅字压浅底"），只给一条主题色的边
            box.setStyleSheet("QGroupBox { border: 1px solid %s; }" % warn_text().name())
        lay = QVBoxLayout(box)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(3)
        tags = card.get("tags") or []
        if tags:
            row = QHBoxLayout()
            row.setSpacing(6)
            for t in tags:
                txt = t[0] if isinstance(t, (list, tuple)) else t
                lb = QLabel(str(txt))
                lb.setObjectName("statusTag")
                lb.setStyleSheet("color: %s; font-size: 11px;" % accent_text().name())
                row.addWidget(lb)
            row.addStretch(1)
            lay.addLayout(row)
        body = QLabel(str(card.get("body") or ""))
        body.setObjectName("statusBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(body)
        return box

    # ── 读数（给自检/探针用）────────────────────────────
    def page_titles(self) -> list:
        return [self.tabs.tabText(i) for i in range(self.tabs.count())]

    def switch_lines(self) -> list:
        return [self.lay_sw.itemAt(i).widget().text()
                for i in range(self.lay_sw.count()) if self.lay_sw.itemAt(i).widget()]

    def snapshot_text(self) -> str:
        try:
            from tool import status_snapshot as SS
            return SS.as_text(self._snap)
        except Exception as e:
            return "取不到：%s" % e

    # ── 按钮 ───────────────────────────────────────────
    def copy_all(self) -> bool:
        """把整页复制成纯文字（贴给我看最方便）"""
        try:
            QApplication.clipboard().setText(self.snapshot_text())
            return True
        except Exception as e:
            print("[状态页] ⚠ 复制失败: %s" % e)
            return False

    def open_data_dir(self) -> bool:
        """打开她的数据目录（内存文件都在里面）"""
        try:
            from tool import status_snapshot as SS
            d = SS.data_dir()
            os.makedirs(d, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(d)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
            return True
        except Exception as e:
            print("[状态页] ⚠ 打开目录失败: %s" % e)
            return False
