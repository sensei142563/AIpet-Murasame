# -*- coding: utf-8 -*-
"""Silicon 新界面：对话框统一外壳 + 过渡动画 + 性能工具。

给所有二级窗口（立绘工坊 / 新建桌宠向导 / 插件设置 / 主题设置 …）提供同一套：
无边框 + 圆角 + 亚克力 + 深色 + 自定义标题栏（可拖动/关闭）→ 与主界面完全一致的观感。
"""
import os

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (QWidget, QDialog, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QGraphicsOpacityEffect, QFrame, QLineEdit)

from .colors import (Color1, Color5, Color8, Gray1, Gray2, RedDark,   # noqa: F401
                     ACCENT_ID, THEME_COLORS, surface_fill)
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
    """启动器底板色：用户自选了 config.ui_bg_color 就用它，否则用当前主题的底色。

    ⚠ 以前这里硬编码回退 "#000000"，把二级窗口的底板刷成纯黑，而经典/樱华主题
      的文字是深色 → 窗口里"字看不见"。回退必须落到主题底色。
    """
    try:
        from .colors import base_bg_color
        return base_bg_color().name()
    except Exception:
        return "#20263a"


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

    def __init__(self, title: str, parent=None, width=760, height=560, opaque=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        # 底板色 = 启动器底板色（用户自选则用它，否则跟随当前主题）
        self._base = QColor(_read_base_color())
        # 注册到全局：外壳改底色时所有已打开窗口一起实时更新
        try:
            _OPEN_DIALOGS.append(self)
        except Exception:
            pass
        # ⚠ 这里原来还有一段"再读一次 config.json"的重复代码，用的是
        #   __file__ 推导路径（frozen 后 __file__ 在 _internal 里 → 永远读不到用户
        #   配置，正是上面注释警告的那件事）。合并成上面的 _read_base_color() 一处，
        #   顺带修掉"绿色版二级窗口不跟随底色"。
        # 不用透明窗口：二级窗口要保证内容清晰（透明窗口在部分环境下会整体发虚/看着透明）
        # 透明窗口 + 圆角底板：四角外保持透明（亚克力可选，圆角始终保留）
        #
        # opaque=True：给**内含 QOpenGLWidget 的窗口**用（目前只有 Live2D 调试器）。
        # 半透明顶层窗口里嵌 GL 子控件，在部分 Windows 显卡驱动上会整块闪白/闪黑
        # （用户报"该显示的地方黑白屏闪"）。opaque 模式下窗口不透明，四角改为填底板色。
        self._opaque = bool(opaque)
        self.setAttribute(Qt.WA_TranslucentBackground, not self._opaque)
        if self._opaque:
            try:
                from PyQt5.QtGui import QPalette
                self.setAutoFillBackground(True)
                _p = self.palette()
                _p.setColor(QPalette.Window, self._base)
                self.setPalette(_p)
            except Exception:
                pass
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
            if color is not None and str(color).strip():
                self._base = QColor(color)
            else:
                # 空值 = 跟随主题 → 回落到主题底板色（不是黑）
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


class MessageDialog(SiliconDialog):
    """主题一致的消息框（用来替掉 QMessageBox）。

    为什么不用 QMessageBox（用户反馈"弹窗看不清字"）：
      · 它按平台风格自绘，正文颜色/字号不受启动器主题控制 → 深色主题下发灰
      · 里面的 emoji 在部分字体环境下渲染成方块（用户截图里那句提示的 📱 就是方块）
    这里用启动器自己的圆角对话框：正文用主题主文字色（SiliconDialog 的调色板已保证
    高对比），细节（路径、原因）单独一段小字并可选中复制。
      · 只有一个按钮时 = 提示框（默认「知道了」）
      · 传了 cancel_text 就是二选一确认框（危险操作把 danger=True，确认键变红）
    正文里**不要用 emoji**，需要强调就用【】或直接写清楚。
    """

    def __init__(self, parent, title, text, detail="", ok_text="知道了", width=470,
                 cancel_text=None, danger=False):
        super().__init__(title, parent, width=width, height=210)
        self.setModal(True)
        lay = self.content
        m = int(M.font_size)
        t = QLabel(text)
        t.setWordWrap(True)
        t.setStyleSheet(f"color: {Color1.name()}; font-size: {m + 1}px;")
        lay.addWidget(t)
        if detail:
            d = QLabel(detail)
            d.setWordWrap(True)
            d.setTextInteractionFlags(Qt.TextSelectableByMouse)   # 路径可以选中复制
            d.setStyleSheet(f"color: {Gray2.name()}; font-size: {m}px;")
            lay.addWidget(d)
        lay.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        if cancel_text:
            # 次要动作在左、主操作在右（Windows 习惯）
            bc = QPushButton(cancel_text)
            bc.setCursor(Qt.PointingHandCursor)
            bc.setMinimumHeight(32)
            bc.setStyleSheet(_dialog_btn_qss(Gray1, outline=True))
            bc.clicked.connect(self.reject)
            row.addWidget(bc)
        b = QPushButton(ok_text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(32)
        b.setStyleSheet(_dialog_btn_qss(RedDark if danger else None))
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)
        try:                       # 按内容量调整高度（细节多的时候别被截断）
            self.adjustSize()
            h = max(200, min(420, self.height() + 10))
            self.resize(max(int(width), self.width()), h)
        except Exception:
            pass


def _dialog_btn_qss(bg=None, outline=False) -> str:
    """对话框里的按钮：主操作 = 强调色（或危险色），次要 = 描边。"""
    m = int(M.font_size)
    if outline:
        return (f"QPushButton {{ background: {surface_fill(175, 24)}; color: {Gray1.name()};"
                f" border: 1px solid {QColor(Gray1.name()).lighter(150).name()};"
                f" border-radius: 8px; padding: 6px 18px; font-size: {m}px; }}"
                f"QPushButton:hover {{ background: {surface_fill(235, 40)}; }}")
    base = bg.name() if bg is not None else accent_hex()
    return (f"QPushButton {{ background: {base}; color: white; border: none;"
            f" border-radius: 8px; padding: 6px 18px; font-size: {m}px; }}"
            f"QPushButton:hover {{ background: {QColor(base).lighter(115).name()}; }}")


def message(parent, title, text, detail="", ok_text="知道了"):
    """显示一个主题一致的消息框（模态）。失败时回退 QMessageBox（内容照旧，不加 emoji）。"""
    try:
        d = MessageDialog(parent, title, text, detail, ok_text)
        return d.exec_()
    except Exception as e:
        print(f"[SiliconUI] ⚠ 消息框失败，回退系统弹窗: {e}")
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(parent, title, text + (("\n\n" + detail) if detail else ""))
        return 0


def confirm(parent, title, text, detail="", ok_text="确定", cancel_text="取消",
            danger=False) -> bool:
    """二选一确认框（替掉 QMessageBox.question）：点「确定」返回 True。

    danger=True 时确认键是红的 —— 删除 / 清空这类不可恢复的操作必须一眼看出危险。
    任何异常都回退系统弹窗，绝不让"确认框打不开"卡住流程。
    """
    try:
        d = MessageDialog(parent, title, text, detail, ok_text,
                          cancel_text=cancel_text, danger=danger)
        return d.exec_() == QDialog.Accepted
    except Exception as e:
        print(f"[SiliconUI] ⚠ 确认框失败，回退系统弹窗: {e}")
        from PyQt5.QtWidgets import QMessageBox
        r = QMessageBox.question(parent, title, text + (("\n\n" + detail) if detail else ""))
        return r == QMessageBox.Yes


def page_msg(parent, title, text, detail=""):
    """页面 / 面板通用的提示框：自动挂到 top-level window 上。

    各页面（桌宠 / 记忆 / 提示词 / 主题 / 插件…）统一用它，别再各写一份，
    也避免有人图省事直接调 QMessageBox（深色主题下发灰、emoji 变方块）。
    """
    try:
        win = parent.window() if parent is not None else None
    except Exception:
        win = parent
    try:
        message(win, title, text, detail)
    except Exception as e:
        print(f"[SiliconUI] ⚠ page_msg 失败: {e}")


def page_confirm(parent, title, text, detail="", ok_text="确定", danger=False) -> bool:
    """页面 / 面板通用的确认框（替代 QMessageBox.question）：点「确定」返回 True。

    danger=True → 确认键变红（删除 / 清空这类不可恢复的动作必须一眼看出危险）。
    任何异常都返回 False：宁可什么都不做，也不要在没确认的情况下执行破坏性操作。
    """
    try:
        win = parent.window() if parent is not None else None
    except Exception:
        win = parent
    try:
        return bool(confirm(win, title, text, detail, ok_text=ok_text, danger=danger))
    except Exception as e:
        print(f"[SiliconUI] ⚠ page_confirm 失败: {e}")
        return False


class InputDialog(SiliconDialog):
    """主题一致的输入框（替掉 QInputDialog.getText）。

    为什么不用 QInputDialog：它按平台风格自绘 —— 白底方框 + 系统按钮，跟启动器的
    深色/主题化界面完全两套；标题栏和字号也不受主题控制。这里用同一个圆角外壳，
    底下放一个主题输入框，回车 = 确定（和 QInputDialog 的习惯一致）。
    """

    def __init__(self, parent, title, label, text="", placeholder="", ok_text="确定",
                 cancel_text="取消", width=470):
        super().__init__(title, parent, width=width, height=190)
        self.setModal(True)
        m = int(M.font_size)
        lay = self.content
        if label:
            lb = QLabel(label)
            lb.setWordWrap(True)
            lb.setStyleSheet(f"color: {Color1.name()}; font-size: {m + 1}px;")
            lay.addWidget(lb)
        self.edit = QLineEdit()
        self.edit.setText(str(text or ""))
        if placeholder:
            self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumHeight(34)
        self.edit.setStyleSheet(
            f"QLineEdit {{ background: rgba(255,255,255,0.06); color: {Color1.name()};"
            f" border: 1px solid {Gray2.name()}; border-radius: 8px;"
            f" padding: 4px 10px; font-size: {m + 1}px; }}"
            f"QLineEdit:focus {{ border: 1px solid {accent_hex()};"
            f" background: rgba(255,255,255,0.10); }}")
        self.edit.returnPressed.connect(self.accept)     # 回车 = 确定
        lay.addWidget(self.edit)
        lay.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        bc = QPushButton(cancel_text)
        bc.setCursor(Qt.PointingHandCursor)
        bc.setMinimumHeight(32)
        bc.setStyleSheet(_dialog_btn_qss(Gray1, outline=True))
        bc.clicked.connect(self.reject)
        row.addWidget(bc)
        b = QPushButton(ok_text)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(32)
        b.setStyleSheet(_dialog_btn_qss())
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)
        try:
            self.adjustSize()
            self.resize(max(int(width), self.width()), max(190, min(320, self.height() + 10)))
        except Exception:
            pass

    def value(self) -> str:
        """输入框里的文本（已去掉首尾空白）"""
        try:
            return self.edit.text().strip()
        except Exception:
            return ""


def ask_text(parent, title, label, text="", placeholder="", ok_text="确定"):
    """主题一致的文本输入（替掉 QInputDialog.getText）：返回 (文本, 是否确定)。

    契约与 QInputDialog.getText 完全一致（返回二元组，取消时 ok=False、文本为空串），
    所以调用点只换名字就行。任何异常都回退系统输入框，绝不把流程卡死。
    """
    try:
        d = InputDialog(parent, title, label, text, placeholder, ok_text)
        if d.exec_() == QDialog.Accepted:
            return d.value(), True
        return "", False
    except Exception as e:
        print(f"[SiliconUI] ⚠ 输入框失败，回退系统弹窗: {e}")
        from PyQt5.QtWidgets import QInputDialog
        return QInputDialog.getText(parent, title, label, text=text)


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


# ── 合并保留：我们这边的配色辅助（无外部引用，留作主题派生用）──
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
