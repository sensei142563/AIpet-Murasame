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

    ⚠ 冻结后 __file__ 位于 _internal 内，直接用它推路径会读不到用户的 config.json，
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
        # ⚠ 冻结(frozen)后 __file__ 在 _internal 里 → 必须用 exe 目录取 config，
        #   否则永远读不到用户设置的底色（这就是"其它窗口不是启动器底色"的原因）
        self._base = QColor(_read_base_color())
        # 注册到全局：外壳改底色时所有已打开窗口一起实时更新
        try:
            _OPEN_DIALOGS.append(self)
        except Exception:
            pass
        # 统一的窗口底色 = 启动器底色（config.ui_bg_color，默认黑）→ 文字一律用高对比浅色
        self._base = QColor("#000000")
        try:
            import json as _json
            _cfg = _json.load(open(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"),
                encoding="utf-8"))
            self._base = QColor(str(_cfg.get("ui_bg_color") or "#000000"))
        except Exception:
            pass
        # 不用透明窗口：二级窗口要保证内容清晰（透明窗口在部分环境下会整体发虚/看着透明）
        # 透明窗口 + 圆角底板：四角外保持透明（亚克力可选，圆角始终保留）
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        try:
            from PyQt5.QtGui import QPalette
            self._apply_palette()
        except Exception as _e:
            print(f"[SiliconUI] ⚠ 对话框调色板设置失败: {_e}")
        self.setModal(False)
        self._drag = None
        self.resize(int(width), int(height))
        self.setMinimumSize(int(width * 0.7), int(height * 0.6))

        # 不再留 10px 透明边距：那圈会显出窗口底色 → 看着像「黑色边框」
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._back = _DlgBack(self)
        # ⚠ 关键：只给“底板自己”上色 —— 之前用 QWidget 选择器会把样式级联到所有子控件
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
            print(f"[SiliconUI] ⚠ 对话框底板上色失败: {_e}")
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
        btn_close = QPushButton("✕")
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
            print(f"[SiliconUI] ⚠ 应用底色失败: {e}")

    def _apply_palette(self):
        from PyQt5.QtGui import QPalette, QFont
        _bg = QColor(self._base)
        _bg.setAlpha(255)
        _dark_bg = _bg.lightness() < 140
        _fg = QColor("#eef1f7") if _dark_bg else QColor("#20242e")
        # ⚠ 配色保持原样（用户要求不要动主题外观）
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
            print(f"[SiliconUI] ⚠ 对话窗口配色失败: {_e}")

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
            fade_in(self, 200)

    def resizeEvent(self, event):
        """窗口尺寸变化后强制「底板 + 所有子布局」重新排布 + 清掉窗口遮罩。

        ⚠ 无边框窗口在显示之后再 resize 时会出现两种毛病：
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
            print(f"[SiliconUI] ⚠ resize 重排失败: {e}")

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
            c = QColor(Color8)
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
    """淡入（用 QGraphicsOpacityEffect；只给单个控件用，避免大范围重绘）"""
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
