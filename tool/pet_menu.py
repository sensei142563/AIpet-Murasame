# -*- coding: utf-8 -*-
"""桌宠右键菜单 —— 圆角 + 剧情模式 UI 风格（奶油面板 / 暗红描边 / 金色饰条 / 菱形标记）

设计取自开发板剧情模式的界面样式（story/web/css/engine.css）实测配色：
    奶油底   linear-gradient(180deg, #fcf8f4, #eee4db)
    描边暗红 #a03a35（55% 透明）
    文字墨棕 #3b2b26 ／ 悬停深红 #7e2b27
    金色饰条 #c9a35f
    条目左侧小红菱形（悬停时更亮）—— 对应 CSS 里的 .mbtn::before

用法：
    from tool.pet_menu import StoryMenu, section, item, submenu
    m = StoryMenu(self)
    section(m, "切换服装")
    item(m, "便服", checked=True)
    s = submenu(m, "装饰（可多选）")
    m.exec_(pos)
"""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QAction, QMenu

# ── 剧情模式配色（与 engine.css 对齐）──
CREAM_TOP = QColor(252, 248, 244, 250)
CREAM_BOT = QColor(238, 228, 219, 250)
INK = QColor(0x3b, 0x2b, 0x26)
INK_SOFT = QColor(0x6b, 0x58, 0x50)
RED = QColor(0xa0, 0x3a, 0x35)
RED_DEEP = QColor(0x7e, 0x2b, 0x27)
GOLD = QColor(0xc9, 0xa3, 0x5f)

RADIUS = 11
SHADOW = 9                      # 四周留给阴影的边距
PANEL_PAD = "9px 8px 9px 8px"   # 面板内边距（QSS）

QSS = """
QMenu {
    background: transparent;
    border: none;
    padding: %s;
}
QMenu::item {
    background: transparent;
    color: #3b2b26;
    padding: 7px 30px 7px 34px;
    margin: 1px 6px;
    border-radius: 7px;
    border: 1px solid transparent;
    font-size: 13px;
}
QMenu::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fffdfb, stop:1 #f6ecdf);
    color: #7e2b27;
    border: 1px solid rgba(160, 58, 53, 0.42);
}
QMenu::item:disabled {
    color: #a03a35;
    background: transparent;
    border: none;
    padding-top: 9px;
    padding-bottom: 6px;
}
QMenu::separator {
    height: 0px;
    border-top: 1px dashed rgba(160, 58, 53, 0.32);
    margin: 7px 16px 7px 16px;
}
QMenu::indicator { width: 0px; height: 0px; }
QMenu::right-arrow { width: 10px; height: 10px; margin-right: 8px; }
""" % PANEL_PAD


class StoryMenu(QMenu):
    """圆角奶油面板菜单；子菜单也应使用本类（见 submenu()）。"""

    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setTitle(title)
        self.setFont(QFont("Microsoft YaHei UI", 10))
        # 无边框 + 透明底：自己画圆角面板与阴影
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(QSS)
        self.setToolTipsVisible(False)
        self._titles = set()          # 作为「小标题」的行（不画菱形）

    # ── 绘制：面板 + 阴影 + 菱形标记 ──
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)
        path = QPainterPath()
        path.addRoundedRect(r, RADIUS, RADIUS)
        # 阴影（多层半透明圆角矩形近似）
        for i in range(SHADOW, 0, -1):
            a = int(4 + 22 * (1.0 - i / float(SHADOW)) ** 2)
            sp = QPainterPath()
            sp.addRoundedRect(r.adjusted(-i * 0.45, -i * 0.30 + 1.2,
                                         i * 0.45, i * 0.90 + 1.2), RADIUS + i * .5, RADIUS + i * .5)
            p.fillPath(sp, QColor(40, 20, 15, a))
        # 面板渐变
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, CREAM_TOP)
        g.setColorAt(1.0, CREAM_BOT)
        p.fillPath(path, QBrush(g))
        # 金色左饰条（对应剧情模式面板的 border-left: 3px solid gold）
        p.save()
        p.setClipPath(path)
        p.fillRect(QRectF(r.left(), r.top(), 3.2, r.height()), GOLD)
        p.restore()
        # 暗红描边
        p.setPen(QPen(QColor(160, 58, 53, 150), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.end()

        # 交给样式绘制条目
        super().paintEvent(ev)

        # 条目左侧菱形标记（标题行不画）
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        active = self.activeAction()
        for act in self.actions():
            if act.isSeparator() or act in self._titles:
                continue
            geo = self.actionGeometry(act)
            if not geo.isValid() or geo.height() <= 0:
                continue
            en = act.isEnabled()
            cx = geo.left() + 17
            cy = geo.center().y() + 1
            s = 4.6 if geo.height() > 26 else 4.0
            dia = QPainterPath()
            dia.moveTo(cx, cy - s)
            dia.lineTo(cx + s, cy)
            dia.lineTo(cx, cy + s)
            dia.lineTo(cx - s, cy)
            dia.closeSubpath()
            if not en:
                continue
            if act.isChecked():                       # 当前选中：实心金菱形
                p.fillPath(dia, QBrush(GOLD))
                p.setPen(QPen(QColor(126, 43, 39, 170), 1.0))
                p.drawPath(dia)
            elif act is active:                       # 悬停：亮红菱形
                p.fillPath(dia, QBrush(RED))
                p.setPen(QPen(QColor(255, 230, 184, 200), 1.0))
                p.drawPath(dia)
            else:                                     # 常态：半透明红菱形
                p.fillPath(dia, QBrush(QColor(RED.red(), RED.green(), RED.blue(), 165)))
        p.end()


def _title_font():
    f = QFont("Microsoft YaHei UI", 9)
    f.setLetterSpacing(QFont.AbsoluteSpacing, 1.4)
    f.setBold(True)
    return f


def section(menu: StoryMenu, text: str):
    """小标题行（不可点，样式为暗红加字距）"""
    a = menu.addAction(text)
    a.setEnabled(False)
    a.setFont(_title_font())
    menu._titles.add(a)
    return a


def item(menu: StoryMenu, text: str, checked: bool = False, enabled: bool = True):
    """普通条目（勾选态用金色菱形表示，不再用 文本）"""
    a = menu.addAction(text)
    a.setCheckable(True)
    a.setChecked(bool(checked))
    a.setEnabled(enabled)
    return a


def submenu(menu: StoryMenu, title: str) -> StoryMenu:
    """添加一个同样风格的子菜单"""
    s = StoryMenu(menu, title)
    s.setTitle(title)
    QMenu.addMenu(menu, s)
    return s


def separator(menu: StoryMenu):
    return menu.addSeparator()


# ── 装饰页（滚动区 + 勾选框）也套用同一套剧情模式配色 ──
DECOR_QSS = """
QScrollArea { background: transparent; border: none; }
QWidget#decorBox { background: transparent; }
QCheckBox {
    color: #3b2b26;
    font-size: 13px;
    padding: 4px 8px;
    border-radius: 6px;
}
QCheckBox:hover { background: rgba(231, 219, 208, 190); }
QCheckBox::indicator {
    width: 14px; height: 14px; border-radius: 4px;
    border: 1px solid rgba(160, 58, 53, 150);
    background: rgba(255, 255, 255, 205);
}
QCheckBox::indicator:checked {
    background: #c9a35f;
    border: 1px solid #7e2b27;
}
QPushButton {
    color: #7e2b27;
    font-size: 12.5px;
    padding: 5px 14px;
    border-radius: 6px;
    border: 1px solid rgba(160, 58, 53, 150);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fffdfb, stop:1 #f6ecdf);
}
QPushButton:hover { background: #fffdfb; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 2px 0 2px 0; }
QScrollBar::handle:vertical { background: rgba(160, 58, 53, 120); border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def style_decor_page(area, box):
    """把「装饰」滚动页套成剧情模式配色（奶油底 + 暗红描边 + 金色勾选）"""
    try:
        area.setStyleSheet(DECOR_QSS)
        area.setFrameShape(area.NoFrame)
        box.setObjectName("decorBox")
        box.setStyleSheet(DECOR_QSS)
    except Exception:
        pass
