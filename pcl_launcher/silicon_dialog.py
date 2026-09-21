# -*- coding: utf-8 -*-
"""Silicon 新界面：对话框统一外壳 + 过渡动画 + 性能工具。

给所有二级窗口（立绘工坊 / 新建桌宠向导 / 插件设置 / 主题设置 …）提供同一套：
无边框 + 圆角 + 亚克力 + 深色 + 自定义标题栏（可拖动/关闭）→ 与主界面完全一致的观感。
"""
import os

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (QWidget, QDialog, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QGraphicsOpacityEffect, QFrame)

from .colors import Color1, Color5, Color8, Gray2, ACCENT_ID, THEME_COLORS  # noqa: F401
from .silicon_ui import M, apply_acrylic


_OPEN_DIALOGS = []          # 已打开的二级窗口（改底色时统一实时刷新）


def _app_base_dir() -> str:
    """程序根目录（打包后 = exe 所在目录；源码 = 项目根）

     冻结后 __file__ 位于 _internal 内，直接用它推路径会读不到用户的 config.json，
    表现就是「其它窗口不跟随启动器底色」。"""
    import sys as _sys
    if getattr(_sys, "frozen", False):
        return os.path.dirname(_sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_base_color() -> str:
    """启动器底色（config.ui_bg_color，默认黑）"""
    try:
        import json as _json
        cfg = _json.load(open(os.path.join(_app_base_dir(), "config.json"), encoding="utf-8"))
        return str(cfg.get("ui_bg_color") or "#000000")
    except Exception:
        return "#000000"


def _theme_bg_hex() -> str:
    """二级窗口的底板色：优先用**当前主题的 Color8**。

     以前这里用 config.ui_bg_color（用户设的启动器底色，默认纯黑）→ 一旦用浅色主题
    （如「千恋万花」：文字深褐 #4a3527、主题底色米白 #fdf6ee），深色文字就画在黑底上，
    整个窗口看起来就是"全黑、什么都没显示"（用户反馈"主题背景调节窗口是黑色"）。
    主题的 Color8 与主题的 Color1 是成对的，跟随它才能保证对比度。
    """
    try:
        c = QColor(Color8)                 # 主题背景色（silicon=深色面 / 千恋万花=米白）
        if c.isValid():
            c.setAlpha(255)
            return c.name()
    except Exception:
        pass
    return _read_base_color()


def theme_plate_colors() -> tuple:
    """二级窗口的（底板色, 文字色）——取**主题自己的原始配色**。

     为什么不用派生配色：`colors.Color1/Color8` 会被「启动器底色」重派生，而
    config 的出厂默认底色就是 #000000 → 整套界面被派生成"黑底浅字"，连浅色主题
    （千恋万花：米白底 + 深褐字）也被覆盖 → 二级窗口成了纯黑一块，和主题完全不符
    （用户反馈"设置背景图片的窗口全黑"）。
    二级窗口按主题原始配色来，才能跟主题一致、内容也清楚。
    """
    try:
        from .colors import _load_theme_palette, current_theme_id
        pal = _load_theme_palette(current_theme_id()) or {}
        bg, fg = str(pal.get("Color8") or ""), str(pal.get("Color1") or "")
        if QColor(bg).isValid():
            return bg, fg
    except Exception as e:
        print(f"[SiliconUI]  读取主题配色失败（回落启动器底色）: {e}")
    return "", ""


def dialog_colors_qss(bg: str, fg: str) -> str:
    """给二级窗口一套「主题底色 + 主题文字色」的局部样式。

    只设底板与**未自带样式的文字**（QLabel 等）；按钮/输入框自己设过样式，
    控件级样式优先级更高，不会被这里覆盖。"""
    if not (bg and fg):
        return ""
    _nl = chr(10)
    return _nl.join([
        "QDialog { background: " + bg + "; }",
        "QLabel, QCheckBox, QRadioButton, QGroupBox { color: " + fg + "; background: transparent; }",
        "QGroupBox::title { color: " + fg + "; }",
    ])


def refresh_all_dialog_colors(color=None):
    """外壳改底色时调用：所有已打开的二级窗口一起换色（实时生效）"""
    for d in list(_OPEN_DIALOGS):
        try:
            d.apply_base_color(color)
        except Exception:
            pass


def accent_hex() -> str:
    return THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")


# ══════════════ 对话框外壳 ══════════════
class SiliconDialog(QDialog):
    """所有二级窗口的基类：无边框圆角亚克力 + 自定义标题栏 + 淡入动画。

    用法：class MyDialog(SiliconDialog): def __init__(...): super().__init__("标题", parent)
    之后照常往 self.content（QVBoxLayout）里塞内容即可。
    """

    def __init__(self, title: str, parent=None, width=760, height=560):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        # 统一的窗口底色 = 启动器底色（config.ui_bg_color，默认黑）→ 文字一律用高对比浅色
        #  冻结(frozen)后 __file__ 在 _internal 里 → 必须用 exe 目录取 config，
        #   否则永远读不到用户设置的底色（这就是"其它窗口不是启动器底色"的原因）
        # 窗口底板 = 启动器底色（config.ui_bg_color；用户明确要求保持黑色底）
        self._base = QColor(_read_base_color())
        self._tfg = ""
        # 注册到全局：换主题/改底色时所有已打开窗口一起实时更新
        try:
            _OPEN_DIALOGS.append(self)
        except Exception:
            pass
        #  用不透明实体窗口。
        #   原来这里开了 WA_TranslucentBackground（想让四角透明做圆角），但 Windows 上
        #   实体透明窗口要走 DWM 合成：部分环境（关掉亚克力 / 某些显卡驱动 / 远程桌面）
        #   会把整窗合成为黑色 → 用户看到的就是「主题背景调节窗口是一片黑，什么都看不清」
        #   （用户反馈）。改成不透明窗口后，绘制不依赖合成器，任何环境都能正常显示；
        #   圆角由底板样式负责，四角只差几个像素，肉眼几乎看不出来。
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAutoFillBackground(True)
        try:
            from PyQt5.QtGui import QPalette
            self._apply_palette()
        except Exception as _e:
            print(f"[SiliconUI]  对话框调色板设置失败: {_e}")
        self.setModal(False)
        self._drag = None
        self.resize(int(width), int(height))
        self.setMinimumSize(int(width * 0.7), int(height * 0.6))

        # 不再留 10px 透明边距：那圈会显出窗口底色 → 看着像「黑色边框」
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._back = _DlgBack(self)
        try:
            self._back._bg_hex = self._base.name()            # 底板绘制用（见 _DlgBack.paintEvent）
        except Exception:
            pass
        #  关键：只给“底板自己”上色 —— 之前用 QWidget 选择器会把样式级联到所有子控件
        #   （标签/输入框被套上底色与圆角），导致二级窗口里的文字看着“消失”。
        try:
            _c = QColor(self._base)
            _c.setAlpha(255)
            self._back.setObjectName("siliconDlgBack")
            self._back.setStyleSheet(
                f"#siliconDlgBack {{ background: {_c.name()}; border: none;"
                f" border-top-left-radius: {M.radius_win}px;"
                f" border-top-right-radius: {M.radius_win}px;"
                f" border-bottom-left-radius: {M.radius_win}px;"
                f" border-bottom-right-radius: {M.radius_win}px; }}")
            self._back.setAttribute(Qt.WA_StyledBackground, True)
        except Exception as _e:
            print(f"[SiliconUI]  对话框底板上色失败: {_e}")
        outer.addWidget(self._back)
        inner = QVBoxLayout(self._back)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        # 标题栏
        bar = QWidget()
        bar.setFixedHeight(46)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 4, 8, 4)
        bl.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet(f"color: {Color1.name()}; font-size: 15px; font-weight: bold;"
                        f" font-family: '{M.font}'; background: transparent;")
        bl.addWidget(t)
        bl.addStretch()
        btn_close = QPushButton("×")
        btn_close.setFixedSize(34, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Color1.name()}; border: none;
                border-radius: 8px; font-size: 14px; }}
            QPushButton:hover {{ background: #e03030; color: white; }}
        """)
        btn_close.clicked.connect(self.reject)
        bl.addWidget(btn_close)
        inner.addWidget(bar)

        # 内容区（外部往这里加）
        self.content = QVBoxLayout()
        self.content.setContentsMargins(18, 6, 18, 16)
        self.content.setSpacing(12)
        holder = QWidget()
        holder.setLayout(self.content)
        inner.addWidget(holder, 1)

        bar.mousePressEvent = self._press
        bar.mouseMoveEvent = self._move
        bar.mouseReleaseEvent = self._release

    def apply_base_color(self, color=None):
        """按启动器底色刷新窗口底色 + 文字对比（可被外壳实时调用）"""
        try:
            from PyQt5.QtGui import QPalette, QFont
            if color is not None:
                self._base = QColor(color)
            else:
                self._base = QColor(_read_base_color())
            try:
                self._back._bg_hex = self._base.name()
                self._back.update()          # 底板重绘
            except Exception:
                pass
            self._apply_palette()
            try:
                c = QColor(self._base)
                c.setAlpha(255)
                self._back.setStyleSheet(
                    f"#siliconDlgBack {{ background: {c.name()}; border: none;"
                    f" border-top-left-radius: {M.radius_win}px;"
                    f" border-top-right-radius: {M.radius_win}px;"
                    f" border-bottom-left-radius: {M.radius_win}px;"
                    f" border-bottom-right-radius: {M.radius_win}px; }}")
                self._back.update()
            except Exception:
                pass
        except Exception as e:
            print(f"[SiliconUI]  应用底色失败: {e}")

    def _apply_palette(self):
        from PyQt5.QtGui import QPalette, QFont
        _bg = QColor(self._base)
        _bg.setAlpha(255)
        _dark_bg = _bg.lightness() < 140
        _fg = QColor("#eef1f7") if _dark_bg else QColor("#20242e")
        #  配色保持原样（用户要求不要动主题外观）
        _field = QColor(self._base).lighter(160) if _dark_bg else QColor(self._base).darker(106)
        pal = QPalette()
        pal.setColor(QPalette.Window, _bg)
        pal.setColor(QPalette.WindowText, _fg)
        pal.setColor(QPalette.Base, _field)
        pal.setColor(QPalette.AlternateBase, _bg)
        pal.setColor(QPalette.Text, _fg)
        pal.setColor(QPalette.Button, _field)
        pal.setColor(QPalette.ButtonText, _fg)
        pal.setColor(QPalette.ToolTipBase, _field)
        pal.setColor(QPalette.ToolTipText, _fg)
        pal.setColor(QPalette.PlaceholderText, QColor(_fg).darker(150))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setFont(QFont(M.font, M.font_size))
        # 颜色规则只设「文字色 / 输入框底色」，避免级联破坏子控件样式
        try:
            self.setStyleSheet(f"""
                QLabel, QCheckBox, QRadioButton, QGroupBox, QTabBar::tab,
                QListWidget, QListView, QTreeWidget {{ color: {_fg.name()}; }}
                QGroupBox {{ border: 1px solid {_field.name()}; border-radius: 8px;
                             margin-top: 12px; padding: 10px 8px 6px 8px; }}
                QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox,
                QComboBox {{ background: {_field.name()}; color: {_fg.name()};
                             border: 1px solid {QColor(_field).lighter(130).name()};
                             border-radius: 8px; padding: 5px 9px; }}
                QPushButton {{ background: {_field.name()}; color: {_fg.name()};
                               border: 1px solid {QColor(_field).lighter(130).name()};
                               border-radius: 8px; padding: 6px 14px; }}
                QPushButton:hover {{ border-color: {_fg.name()}; }}
                QListWidget::item:selected {{ background: rgba(90,150,255,0.35); }}
                QMenu {{ background: {_field.name()}; color: {_fg.name()}; }}
                QToolTip {{ background: {_field.name()}; color: {_fg.name()}; }}
            """)
        except Exception as _e:
            print(f"[SiliconUI]  对话窗口配色失败: {_e}")

    def closeEvent(self, event):
        try:
            if self in _OPEN_DIALOGS:
                _OPEN_DIALOGS.remove(self)
        except Exception:
            pass
        super().closeEvent(event)

    # 拖动
    def _press(self, e):
        self._drag = e.globalPos() - self.frameGeometry().topLeft()

    def _move(self, e):
        if self._drag is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPos() - self._drag)

    def _release(self, e):
        self._drag = None

    # 淡入 + 亚克力
    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_silicon_done", False):
            self._silicon_done = True
            # 对话框不做亚克力：亚克力会让窗口半透明（用户反馈「界面变透明了」），
            # 这里用不透明主题色底板，保证内容清晰可读。
            try:
                fade_in(self, 200)
            except Exception:
                pass
            # 兜底自检：1.5 秒后若窗口上还挂着图形特效，强制摘掉
            # （QGraphicsOpacityEffect 挂在顶层窗口上会导致整窗黑屏）
            def _clear_effect_guard():
                try:
                    if self.graphicsEffect() is not None:
                        self.setGraphicsEffect(None)
                        print("[SiliconUI] 已摘掉窗口上的图形特效（防止黑窗）")
                        self.update()
                except Exception:
                    pass
            try:
                from PyQt5.QtCore import QTimer as _QT
                _QT.singleShot(1500, _clear_effect_guard)
            except Exception:
                pass

    def resizeEvent(self, event):
        """窗口尺寸变化后强制「底板 + 所有子布局」重新排布 + 清掉窗口遮罩。

         无边框窗口在显示之后再 resize 时会出现两种毛病：
        ① 子控件停在旧尺寸/旧位置 → 「按钮还是小窗口时的大小和位置」；
        ② Windows 残留旧窗口区域/遮罩 → 「看到的位置」和「点得到的位置」不一致。
        所以这里既重排、又 clearMask 并重绘一次。
        """
        super().resizeEvent(event)
        try:
            back = getattr(self, "_back", None)
            if back is not None:
                back.setGeometry(0, 0, self.width(), self.height())
                lay_b = back.layout()
                if lay_b is not None:
                    lay_b.activate()
            lay = self.layout()
            if lay is not None:
                lay.activate()
            c = getattr(self, "content", None)
            if c is not None:
                c.invalidate()
                c.activate()
            for w in self.findChildren(QWidget):
                if w is not self:
                    w.updateGeometry()
            try:
                self.clearMask()          # 清掉旧遮罩/区域（否则点击命中会错位）
            except Exception:
                pass
            self.update()
        except Exception as e:
            print(f"[SiliconUI]  resize 重排失败: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


class _DlgBack(QWidget):
    """对话框圆角底"""

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), M.radius_win, M.radius_win)
            #  用"主题原始底色"（由对话框初始化时塞进来），绝不能用全局 Color8：
            #   全局 Color8 会被"启动器底色"重派生（出厂默认 #000000）→ 底板被填成纯黑，
            #   浅色主题下整个二级窗口就是黑的一块（用户反馈"设置背景的窗口全黑"）。
            c = QColor(getattr(self, "_bg_hex", "") or Color8)
            c.setAlpha(255)          # 强制不透明：避免背景透出来看着像「界面透明」
            p.fillPath(path, c)
            # 顶部一条细强调线，和主界面呼应
            try:
                acc = QColor(THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0"))
                p.setPen(acc)
                p.drawLine(14, 1, self.width() - 14, 1)
            except Exception:
                pass
            p.end()
        except Exception:
            pass


# ══════════════ 过渡动画 ══════════════
def fade_in(widget: QWidget, ms: int = 200, start: float = 0.0):
    """淡入。

     顶层窗口（对话框）绝对不能用 QGraphicsOpacityEffect：Qt 官方不支持给顶层窗口加
      图形特效，Windows 上会把整窗渲染成**纯黑**（用户反馈"主题背景设置窗口全黑"）。
      顶层窗口一律改用 windowOpacity 动画（官方支持、不依赖特效缓冲）。
      非顶层控件才走 QGraphicsOpacityEffect。
    """
    try:
        if widget.isWindow():
            widget.setWindowOpacity(float(start))
            anim = QPropertyAnimation(widget, b"windowOpacity", widget)
            anim.setDuration(max(60, int(ms)))
            anim.setStartValue(float(start))
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            widget._fade_anim = anim        # 防 GC
            return anim
    except Exception as _e:
        print(f"[SiliconUI]  窗口淡入失败（直接显示）: {_e}")
        try:
            widget.setWindowOpacity(1.0)
        except Exception:
            pass
        return None
    try:
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(start)
        widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(max(60, int(ms)))
        anim.setStartValue(start)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        widget._fade_anim = anim        # 防 GC
        return anim
    except Exception:
        return None


def slide_fade_in(widget: QWidget, ms: int = 200, dx: int = 18):
    """上滑 + 淡入。顶层窗口只做 windowOpacity（见 fade_in 的说明）。"""
    if widget.isWindow():
        return fade_in(widget, ms, 0.0)
    return _slide_fade_in_inner(widget, ms, dx)


def _slide_fade_in_inner(widget: QWidget, ms: int = 200, dx: int = 18):
    """淡入 + 轻微横向滑入（页面切换用）"""
    try:
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
        a1 = QPropertyAnimation(eff, b"opacity", widget)
        a1.setDuration(int(ms))
        a1.setStartValue(0.0)
        a1.setEndValue(1.0)
        a1.setEasingCurve(QEasingCurve.OutCubic)
        a1.finished.connect(lambda: widget.setGraphicsEffect(None))
        a1.start(QPropertyAnimation.DeleteWhenStopped)
        widget._fade_anim = a1
        return a1
    except Exception:
        return None
