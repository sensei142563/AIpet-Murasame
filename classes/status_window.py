# -*- coding: utf-8 -*-
"""「她的状态 · 记忆 · 提醒」窗口 —— **剧情模式 UI 风格**（像 galgame 的系统页）。

风格来源：本项目剧情模式的样式表 `story/web/css/engine.css`（照抄实测配色，不是自创）：
    奶油面版  linear-gradient(180deg, #f4ece5, #e7dbd0)   --cream / --cream-2
    墨棕正文  #3b2b26   次要文字 #6b5850                   --ink / --ink-soft
    暗红描边  #a03a35（rgba 55%）／ 悬停深红 #7e2b27        --red / --red-deep
    金色饰条  #c9a35f                                     --gold
    卡片      1px 暗红描边 + 8px 圆角 + 轻投影（.card）
    小标题    加字距的棕字 + 左侧红色菱形（.mbtn::before 的那颗菱形）
    正文      衬线体（--story-font：思源宋体 → Noto Serif → 宋体）
    标签      红/金小胶囊（.tag / .tag.gold）

为什么单独开窗（用户要求）：状态/记忆/提醒内容长，塞在对话框里会把她的台词挤掉。

数据全部来自她自己的模块（state / desire / care / reminder / self_learn / experience /
autonomy），这里只负责显示；读不到的模块就跳过，不让窗口崩。
"""
import html
import re

from PyQt5.QtCore import QPointF, QPropertyAnimation, QRectF, Qt, pyqtProperty
from PyQt5.QtGui import (QBrush, QColor, QFont, QFontDatabase, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QPolygonF)
from PyQt5.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QSizeGrip, QStackedWidget, QVBoxLayout, QWidget)

# ── 剧情模式配色（与 engine.css / tool/pet_menu.py 完全一致）──
CREAM_TOP = QColor(244, 236, 229, 250)
CREAM_BOT = QColor(231, 219, 208, 250)
INK = QColor(0x3b, 0x2b, 0x26)
INK_SOFT = QColor(0x6b, 0x58, 0x50)
RED = QColor(0xa0, 0x3a, 0x35)
RED_DEEP = QColor(0x7e, 0x2b, 0x27)
GOLD = QColor(0xc9, 0xa3, 0x5f)

SHADOW = 10
RADIUS = 12

# 剧情模式的正文衬线体（engine.css 的 --story-font 顺序）
_STORY_FAMS = ("Source Han Serif SC", "Noto Serif CJK SC", "Noto Serif SC",
               "Songti SC", "SimSun", "Microsoft YaHei UI")
_UI_FAMS = ("Microsoft YaHei UI", "Microsoft YaHei", "SimHei")

_window = None          # 单例：桌宠那边只留一个窗口


def _pick_font(fams, size, bold=False):
    """从候选里挑一个系统真装了的字体（挑不到就交给 Qt 自己回退）"""
    try:
        have = set(QFontDatabase().families())
        for f in fams:
            if f in have:
                fnt = QFont(f, size)
                fnt.setBold(bool(bold))
                return fnt
    except Exception:
        pass
    fnt = QFont(fams[-1], size)
    fnt.setBold(bool(bold))
    return fnt


def _story_font(size=10, bold=False):
    return _pick_font(_STORY_FAMS, size, bold)


def _ui_font(size=10, bold=False):
    return _pick_font(_UI_FAMS, size, bold)


def _rich(text: str, max_lines: int = 300) -> str:
    """把纯文本转成剧情风格的小富文本：【小标题】染成深红加粗，其余保持墨棕"""
    out = []
    for ln in str(text or "").splitlines()[:max_lines]:
        esc = html.escape(ln)
        m = re.match(r"^【(.+?)】(.*)$", esc)
        if m:
            head = m.group(1)
            rest = m.group(2).strip()
            if out:
                out.append('<div style="height:6px"></div>')
            out.append(f'<div style="color:#7e2b27;font-weight:600">{head}</div>')
            if rest:
                out.append(f"<div>{rest}</div>")
        elif not esc.strip():
            out.append('<div style="height:6px"></div>')
        else:
            out.append(f"<div>{esc}</div>")
    return "".join(out)


def _diamond(color=RED, size=9) -> QPixmap:
    """那颗红色小菱形（剧情模式条目标记）"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size / 2.0 - 0.6
    poly = QPolygonF([QPointF(size / 2.0, size / 2.0 - s),
                      QPointF(size / 2.0 + s, size / 2.0),
                      QPointF(size / 2.0, size / 2.0 + s),
                      QPointF(size / 2.0 - s, size / 2.0)])
    p.setBrush(QBrush(color))
    p.setPen(QPen(QColor(255, 230, 184, 180), 0.8))
    p.drawPolygon(poly)
    p.end()
    return pm


# ── QSS：卡片 / 标签 / 按钮 / 滚动条（全部按 engine.css 配色）──
QSS = """
QWidget#panel { background: transparent; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(250,246,242,235),
                                stop:1 rgba(244,236,229,225));
    border: 1px solid rgba(160,58,53,110);
    border-radius: 8px;
}
QLabel#cardTitle { color: #3b2b26; }
QLabel#body { color: #3b2b26; }
QLabel#sub { color: #6b5850; }
QLabel#tagRed {
    color: #7e2b27; background: rgba(160,58,53,26);
    border: 1px solid rgba(160,58,53,72); border-radius: 9px; padding: 2px 10px;
}
QLabel#tagGold {
    color: #8a6a24; background: rgba(201,163,95,41);
    border: 1px solid rgba(201,163,95,102); border-radius: 9px; padding: 2px 10px;
}
QPushButton {
    color: #7e2b27; padding: 6px 16px; border-radius: 6px;
    border: 1px solid rgba(160,58,53,150);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fffdfb, stop:1 #f6ecdf);
}
QPushButton:hover { background: #fffdfb; }
QPushButton:pressed { background: #f0e2d2; }
/* 顶部分类页按钮：没选中的低调一点，选中的用金色底 + 深红字（剧情模式的选中感） */
QPushButton#tabBtn {
    color: #6b5850; padding: 5px 14px; border-radius: 7px;
    border: 1px solid rgba(160,58,53,60); background: transparent;
}
QPushButton#tabBtn:hover { background: rgba(255,253,251,200); color: #7e2b27; }
QPushButton#tabBtn:checked {
    color: #7e2b27; font-weight: bold;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,253,251,255), stop:1 rgba(246,236,223,255));
    border: 1px solid rgba(201,163,95,230);
}
QScrollBar:vertical { width: 8px; background: transparent; margin: 2px 0 2px 0; }
QScrollBar::handle:vertical { background: rgba(160,58,53,120); border-radius: 4px; min-height: 26px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


class _Card(QFrame):
    """一张剧情风格的卡片：标题（带红菱形）+ 标签行 + 正文"""

    def __init__(self, title: str, body: str = "", tags=(), parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 11, 14, 13)
        lay.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(7)
        dia = QLabel(self)
        dia.setPixmap(_diamond(RED, 9))
        dia.setFixedSize(9, 9)
        head.addWidget(dia)
        t = QLabel(str(title), self)
        t.setObjectName("cardTitle")
        f = _ui_font(10, True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        t.setFont(f)
        head.addWidget(t)
        head.addStretch(1)
        for txt, obj in tags or ():
            g = QLabel(str(txt), self)
            g.setObjectName(obj)
            g.setFont(_ui_font(8, False))
            head.addWidget(g)
        lay.addLayout(head)

        lab = QLabel(self)
        lab.setObjectName("body")
        lab.setFont(_story_font(10))
        lab.setTextFormat(Qt.RichText)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lab.setText(_rich(body))
        lay.addWidget(lab)


class StatusWindow(QDialog):
    """她的状态 / 习惯 / 记忆 / 提醒（剧情模式风格的独立窗口 + 顶部分类页）。"""

    TABS = ("状态", "习惯", "记忆", "提醒")

    def __init__(self, parent=None, on_study=None):
        super().__init__(parent)
        self._on_study = on_study
        self.setWindowTitle("丛雨 · 状态 · 习惯 · 记忆 · 提醒")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(QSS)
        self.setMinimumSize(560, 460)
        self.resize(700, 640)
        self._drag = None
        self._tab_idx = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW + 6, SHADOW + 6, SHADOW + 6, SHADOW + 6)
        outer.setSpacing(8)
        self._box = QVBoxLayout()
        self._box.setSpacing(8)
        outer.addLayout(self._box)

        # ── 顶部：标题 + 关闭 ──
        head = QHBoxLayout()
        head.setSpacing(8)
        d2 = QLabel(self)
        d2.setPixmap(_diamond(GOLD, 11))
        d2.setFixedSize(11, 11)
        head.addWidget(d2)
        self.lb_title = QLabel("她的状态", self)
        self.lb_title.setObjectName("cardTitle")
        _tf = _ui_font(12, True)
        _tf.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        self.lb_title.setFont(_tf)
        head.addWidget(self.lb_title)
        head.addStretch(1)
        self.btn_close = QPushButton("关闭", self)
        self.btn_close.clicked.connect(self.close)
        head.addWidget(self.btn_close)
        self._box.addLayout(head)

        # 金色分隔线（剧情模式的金色饰条）
        line = QFrame(self)
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(201,163,95,190); border: none;")
        self._box.addWidget(line)

        self.lb_sub = QLabel("", self)
        self.lb_sub.setObjectName("sub")
        self.lb_sub.setFont(_ui_font(9))
        self.lb_sub.setWordWrap(True)
        self._box.addWidget(self.lb_sub)

        # ── ★ 顶部分类页（用户要求：属性分类预览）──
        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self.tab_btns = []
        for i, name in enumerate(self.TABS):
            b = QPushButton(name, self)
            b.setObjectName("tabBtn")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setFont(_ui_font(9))
            b.clicked.connect(lambda _=False, k=i: self.set_tab(k))
            tab_row.addWidget(b)
            self.tab_btns.append(b)
        tab_row.addStretch(1)
        self._box.addLayout(tab_row)

        # ── 每页一个滚动区（各自独立滚动，互不影响）──
        self.stack = QStackedWidget(self)
        self.pages = []          # [(scroll, cards_layout, holder)]
        for _name in self.TABS:
            area = QScrollArea(self)
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            holder = QWidget(area)
            holder.setObjectName("panel")
            cards = QVBoxLayout(holder)
            cards.setContentsMargins(2, 2, 4, 2)
            cards.setSpacing(10)
            cards.addStretch(1)
            area.setWidget(holder)
            self.stack.addWidget(area)
            self.pages.append((area, cards, holder))
        self._box.addWidget(self.stack, 1)

        # ── 底部按钮（一律横排）──
        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_study = QPushButton("让她现在学一次", self)
        self.btn_study.clicked.connect(self._study)
        self.btn_save = QPushButton("打开记忆文件", self)
        self.btn_save.clicked.connect(self._open_file)
        self.btn_refresh = QPushButton("刷新", self)
        self.btn_refresh.clicked.connect(self.refresh)
        for b in (self.btn_study, self.btn_save, self.btn_refresh):
            b.setFont(_ui_font(9))
            row.addWidget(b)
        row.addStretch(1)
        grip = QSizeGrip(self)
        row.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)
        self._box.addLayout(row)

        self.refresh()
        # 淡入（剧情模式那种柔和出现）
        try:
            self.setWindowOpacity(0.0)
            self._anim = QPropertyAnimation(self, b"windowOpacity", self)
            self._anim.setDuration(220)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.start()
        except Exception:
            self.setWindowOpacity(1.0)

    # ── 分类页 ──
    def set_tab(self, idx: int):
        try:
            idx = max(0, min(len(self.TABS) - 1, int(idx)))
            self._tab_idx = idx
            self.stack.setCurrentIndex(idx)
            for i, b in enumerate(self.tab_btns):
                b.setChecked(i == idx)
            self.lb_title.setText("她的" + self.TABS[idx] if idx else "她的状态")
        except Exception:
            pass

    # ── 自己画外框：奶油渐变面板 + 暗红描边 + 金色左饰条 + 投影 ──
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)
        path = QPainterPath()
        path.addRoundedRect(r, RADIUS, RADIUS)
        for i in range(SHADOW, 0, -1):
            a = int(4 + 22 * (1.0 - i / float(SHADOW)) ** 2)
            sp = QPainterPath()
            sp.addRoundedRect(r.adjusted(-i * 0.5, -i * 0.34 + 1.4, i * 0.5, i * 1.0 + 1.4),
                              RADIUS + i * 0.5, RADIUS + i * 0.5)
            p.fillPath(sp, QColor(40, 20, 15, a))
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, CREAM_TOP)
        g.setColorAt(1.0, CREAM_BOT)
        p.fillPath(path, QBrush(g))
        p.save()
        p.setClipPath(path)
        p.fillRect(QRectF(r.left(), r.top(), 3.2, r.height()), GOLD)
        p.restore()
        p.setPen(QPen(QColor(160, 58, 53, 165), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.end()

    # 无边框窗口：拖标题栏移动
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.pos().y() < 52 + SHADOW:
            self._drag = ev.globalPos() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self._drag is not None and (ev.buttons() & Qt.LeftButton):
            self.move(ev.globalPos() - self._drag)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag = None

    # ── 数据 → 卡片 ──
    def _clear(self):
        for _area, cards, _holder in self.pages:
            while cards.count():
                it = cards.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.setParent(None)

    def _subtitle(self) -> str:
        bits = []
        try:
            from tool import care as _care
            bits.append("在一起第 %d 天" % _care.companion_days())
        except Exception:
            pass
        try:
            from tool import state as _st
            bits.append("心情：%s" % _st.mood_label())
            bits.append("关系：%s" % _st.affinity_label())
        except Exception:
            pass
        try:
            from tool import desire as _dz
            bits.append("活跃度：%s" % _dz.level_label())
        except Exception:
            pass
        return "　·　".join(bits)

    def _cards_of(self, idx: int):
        """第 idx 页的卡片容器（返回 (cards_layout, holder)）"""
        _area, cards, holder = self.pages[max(0, min(len(self.pages) - 1, int(idx)))]
        return cards, holder

    def refresh(self):
        """重新采集数据，按分类页铺卡片"""
        try:
            self._clear()
            try:
                self.lb_sub.setText(self._subtitle())
            except Exception:
                pass

            # ══════ 第 1 页：状态 ══════
            cards, holder = self._cards_of(0)
            tags, body = [], []
            try:
                from tool import state as _st
                tags.append(("心情 %d" % int(_st.mood()), "tagRed"))
                tags.append(("关系 %d" % int(_st.affinity()), "tagRed"))
            except Exception:
                pass
            try:
                from tool import care as _care
                tags.append(("第 %d 天" % _care.companion_days(), "tagGold"))
                if _care.meeting_mode():
                    tags.append(("会议静音中", "tagGold"))
            except Exception:
                pass
            try:
                from tool import desire as _dz
                tags.append(("活跃度 %s" % _dz.level_label(), "tagGold"))
            except Exception:
                pass
            try:
                from tool import state as _st
                body.append("【上次说话】" + _st.summary())
            except Exception:
                pass
            try:
                from tool import self_learn as _sl
                w = _sl.working()
                if w:
                    body.append("【手上的事】" + str(w.get("task"))[:70]
                                + ("（做成了）" if w.get("ok") else "（没做成）"))
            except Exception:
                pass
            try:
                from tool import care as _care
                body.append("【陪伴】" + _care.summary_text())
            except Exception:
                pass
            if body or tags:
                cards.addWidget(_Card("现在", chr(10).join(body), tags, holder))
            try:
                from tool import desire as _dz
                cards.addWidget(_Card("她现在的念头", _dz.summary_text(), (), holder))
            except Exception:
                pass
            try:
                from tool import autonomy as _au
                cards.addWidget(_Card("她能自己做到哪一步", _au.summary_text(), (), holder))
            except Exception:
                pass
            cards.addStretch(1)

            # ══════ 第 2 页：习惯（自主学习记录的主人习惯）══════
            cards, holder = self._cards_of(1)
            try:
                from tool import habits as _hb
                cards.addWidget(_Card("主人的习惯（她自己观察攒的）",
                                      _hb.summary_text(), (), holder))
                # 分卡片展示，看起来清楚
                sch = _hb.schedule_text()
                hrs = _hb.hours_text()
                if sch or hrs:
                    cards.addWidget(_Card("作息与活跃时段",
                                          (("【作息】" + sch) if sch else "")
                                          + (chr(10) + "【活跃时段】" + hrs if hrs else ""),
                                          (), holder))
                apps = _hb.apps_text(6)
                if apps:
                    cards.addWidget(_Card("常用软件", apps, (), holder))
                mus = _hb.music_text()
                if mus:
                    cards.addWidget(_Card("爱听的歌", mus, (), holder))
            except Exception as _e1:
                cards.addWidget(_Card("习惯", f"（读不到：{type(_e1).__name__}）", (), holder))
            cards.addStretch(1)

            # ══════ 第 3 页：记忆 ══════
            cards, holder = self._cards_of(2)
            mem = []
            try:
                from tool import self_learn as _sl
                prof = _sl.profile_text()
                if prof:
                    mem.append("【对主人的印象】" + prof)
                eps = _sl.episodes(6)
                if eps:
                    mem.append("【最近发生的事】")
                    for e in eps:
                        import time as _t
                        try:
                            ts = _t.strftime("%m-%d %H:%M", _t.localtime(float(e.get("ts") or 0)))
                        except Exception:
                            ts = ""
                        mem.append("· " + ts + " " + str(e.get("text"))[:100])
                try:
                    d = _sl.diary_of()
                    if d:
                        mem.append("【今天的日记】" + d[:400])
                except Exception:
                    pass
            except Exception:
                pass
            try:
                from tool import music as _mu
                fav = _mu.favorites_text(8)
                if fav:
                    mem.append("【爱听的歌】" + fav)
            except Exception:
                pass
            cards.addWidget(_Card("她记下的事", chr(10).join(mem) or "（还什么都没记下）",
                                  (), holder))
            try:
                from tool import experience as _exp
                cards.addWidget(_Card("她学会的做法（任务经验）",
                                      _exp.summary_text(8), (), holder))
            except Exception:
                pass
            cards.addStretch(1)

            # ══════ 第 4 页：提醒 ══════
            cards, holder = self._cards_of(3)
            try:
                from tool import reminder as _rm
                cards.addWidget(_Card("挂着的提醒", _rm.list_text(), (), holder))
            except Exception:
                pass
            try:
                from tool import care as _care
                cards.addWidget(_Card("关怀与陪伴", _care.summary_text(), (), holder))
            except Exception:
                pass
            cards.addStretch(1)

            self.set_tab(self._tab_idx)
            try:
                from tool import self_learn as _sl
                print(f"[状态窗] 已刷新（记忆文件：{_sl._store_path()}）")
            except Exception:
                pass
        except Exception as e:
            print(f"[状态窗] ⚠ 刷新失败: {type(e).__name__}: {e}")

    def _study(self):
        try:
            if self._on_study:
                self._on_study()
                self.lb_sub.setText("唔……我去翻两页书，等一下下再点「刷新」。")
        except Exception as e:
            self.lb_sub.setText("自习没跑起来：%s" % e)

    def _open_file(self):
        import os
        try:
            from tool import self_learn as _sl
            p = _sl._store_path()
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write('{"notes": [], "diary": {}}')
            os.startfile(p)
        except Exception as e:
            self.lb_sub.setText("打不开文件：%s" % e)


def show_status_window(parent=None, on_study=None):
    """打开（或重新刷新并前置）这一扇窗口 —— 桌宠菜单里那一项走这里"""
    global _window
    try:
        if _window is None:
            _window = StatusWindow(parent, on_study=on_study)
        else:
            _window.refresh()
            try:
                _window.setWindowOpacity(1.0)
            except Exception:
                pass
        _window.showNormal()
        _window.raise_()
        _window.activateWindow()
        return _window
    except Exception as e:
        print(f"[状态窗] ⚠ 打不开: {type(e).__name__}: {e}")
        return None
