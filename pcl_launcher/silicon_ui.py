# -*- coding: utf-8 -*-
"""Silicon 风格 UI 层（参考 PyQt-SiliconUI 的设计语言：亚克力模糊 + 圆角 + 强调色 + 动效控件）。

本模块只做“外观”，不改任何业务逻辑：
- apply_acrylic(win)   : 给窗口开亚克力模糊（Win10/11）+ Win11 圆角
- install(app)         : 安装全局 QSS（滚动条/下拉/输入框/菜单/滑块/提示…）
- nav_pill_qss()       : 顶部导航按钮的胶囊风格（选中=强调色胶囊）
- card_qss()           : 卡片容器（半透明面 + 1px 描边 + 圆角）
- shadow(widget)       : 柔和投影
- metrics              : 圆角/间距等设计常量
"""
import ctypes
import os
import sys

from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QApplication, QGraphicsDropShadowEffect, QWidget,
                             QLabel, QAbstractButton)

# ── 设计常量（圆角/间距/字号，改这里就能整体调风格）──
class M:
    radius_win = 14        # 窗口圆角
    radius_card = 12       # 卡片
    radius_ctrl = 8        # 按钮/输入框
    pad = 12               # 常规内边距
    gap = 8                # 常规间距
    font = "Microsoft YaHei UI"
    font_size = 13


def _argb(hex_or_rgba, alpha=None):
    """(颜色文本, 透明度 0-255) → ABGR 整数（SetWindowCompositionAttribute 用）"""
    c = QColor(hex_or_rgba) if not str(hex_or_rgba).startswith("rgba") else QColor(hex_or_rgba)
    a = int(alpha if alpha is not None else (c.alpha() or 255))
    return (a << 24) | (c.blue() << 16) | (c.green() << 8) | c.red()


def apply_round_corners(win, radius=None):
    """只做「圆角 + 深色标题栏」（Win11 DWM，几乎零开销）—— 与模糊解耦，
    这样关掉亚克力（省性能）时窗口依然是圆角，不会变成直角方框。"""
    try:
        if os.name != "nt":
            return False
        hwnd = int(win.winId())
        r = int(radius if radius is not None else M.radius_win)
        v = ctypes.c_int(2 if r else 1)      # 2=圆角, 1=直角
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(v), ctypes.sizeof(v))
        dark = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        return True
    except Exception:
        return False


def apply_acrylic(win, tint="#161a24", alpha=205, radius=None):
    """给窗口开启亚克力模糊 + 圆角（Windows 10/11）。

    失败时静默返回 False（任何异常都不影响启动）。
    """
    try:
        if os.name != "nt":
            return False
        win.setAttribute(Qt.WA_TranslucentBackground, True)
        hwnd = int(win.winId())

        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint),
                        ("AnimationId", ctypes.c_int)]

        class WINCOMPATTRDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int),
                        ("Data", ctypes.POINTER(ACCENT_POLICY)),
                        ("SizeOfData", ctypes.c_size_t)]

        ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
        WCA_ACCENT_POLICY = 19
        policy = ACCENT_POLICY()
        policy.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
        policy.AccentFlags = 2
        policy.GradientColor = _argb(tint, alpha)
        policy.AnimationId = 0
        data = WINCOMPATTRDATA(WCA_ACCENT_POLICY, ctypes.pointer(policy),
                               ctypes.sizeof(policy))
        try:
            ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        except Exception:
            pass
        # Win11：圆角偏好 + 深色标题栏
        try:
            r = int(radius if radius is not None else M.radius_win)
            v = ctypes.c_int(2 if r else 1)     # 2=圆角, 1=直角
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(v), ctypes.sizeof(v))
            dark = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[SiliconUI] 亚克力效果不可用（不影响使用）: {e}")
        return False


def shadow(widget: QWidget, blur=30, dy=8, alpha=110, color="#000000"):
    """柔和投影（很多控件上叠加太多会卡，只建议给卡片/对话框用）"""
    try:
        eff = QGraphicsDropShadowEffect(widget)
        eff.setBlurRadius(blur)
        eff.setOffset(0, dy)
        c = QColor(color)
        c.setAlpha(alpha)
        eff.setColor(c)
        widget.setGraphicsEffect(eff)
        return eff
    except Exception:
        return None


# ══════════════════════ 全局 QSS ══════════════════════
def silicon_qss(accent="#4c8dff", text="#e6eaf2", text_dim="#a9b2c6",
                surface="#20263a", surface2="#1a1f2e", bg="#161a24",
                border="#39405a", radius=None) -> str:
    """现代 QSS：只覆盖“Qt 默认皮肤”那部分控件（业务自带内联样式的优先）"""
    r = int(radius if radius is not None else M.radius_ctrl)
    f = M.font
    return f"""
/* ===== 全局 ===== */
* {{ font-family: "{f}", "Microsoft YaHei", sans-serif; }}
QWidget {{ color: {text}; font-size: {M.font_size}px; }}
QToolTip {{
    background: {surface2}; color: {text}; border: 1px solid {border};
    border-radius: {r}px; padding: 6px 9px;
}}
/* ===== 滚动条（细长圆角，悬停加亮）===== */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.18); border-radius: 5px; min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{ background: {accent}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.18); border-radius: 5px; min-width: 36px;
}}
QScrollBar::handle:horizontal:hover {{ background: {accent}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ===== 输入类 ===== */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: rgba(255,255,255,0.05); border: 1px solid {border};
    border-radius: {r}px; padding: 6px 10px; selection-background-color: {accent};
}}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {accent}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {accent}; background: rgba(255,255,255,0.08);
}}
QComboBox {{
    background: rgba(255,255,255,0.05); border: 1px solid {border};
    border-radius: {r}px; padding: 5px 10px; min-height: 22px;
}}
QComboBox:hover {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {text_dim}; margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {surface}; border: 1px solid {border}; border-radius: {r}px;
    selection-background-color: {accent}; selection-color: white; outline: none;
    padding: 4px;
}}
/* ===== 勾选框（圆角小方框 + 强调色对勾底）===== */
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{
    border: 1px solid {border}; border-radius: 4px; background: rgba(255,255,255,0.06);
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}
QRadioButton::indicator {{ border-radius: 8px; border: 1px solid {border};
    background: rgba(255,255,255,0.06); }}
QRadioButton::indicator:checked {{ background: {accent}; border: 4px solid {surface}; }}

/* ===== 滑块（细轨道 + 强调色已选段 + 圆点手柄）===== */
QSlider::groove:horizontal {{
    height: 5px; background: rgba(255,255,255,0.14); border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: white; width: 14px; height: 14px; margin: -6px 0;
    border-radius: 7px; border: 2px solid {accent};
}}
QSlider::handle:horizontal:hover {{ background: {accent}; }}

/* ===== 菜单（悬浮卡片）===== */
QMenu {{
    background: {surface}; border: 1px solid {border}; border-radius: {r}px; padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accent}; color: white; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 8px; }}

/* ===== 列表 ===== */
QListWidget, QListView, QTreeWidget {{
    background: rgba(255,255,255,0.03); border: 1px solid {border};
    border-radius: {r}px; outline: none; padding: 4px;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {accent}; color: white; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.08); }}

/* ===== 分组框（扁平标题 + 细描边）===== */
QGroupBox {{
    border: 1px solid {border}; border-radius: {r + 2}px; margin-top: 14px;
    padding: 12px 10px 8px 10px; background: rgba(255,255,255,0.03);
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {text_dim};
}}

/* ===== 进度条 ===== */
QProgressBar {{
    background: rgba(255,255,255,0.10); border: none; border-radius: 6px;
    height: 12px; text-align: center; color: {text};
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 6px; }}

/* ===== 标签页 ===== */
QTabWidget::pane {{ border: 1px solid {border}; border-radius: {r}px; top: -1px; }}
QTabBar::tab {{
    background: transparent; padding: 7px 16px; margin-right: 4px;
    border-top-left-radius: {r}px; border-top-right-radius: {r}px; color: {text_dim};
}}
QTabBar::tab:selected {{ background: {surface}; color: {text}; }}
QTabBar::tab:hover {{ color: {text}; }}

/* ===== 文件对话框等系统窗口里的按钮 ===== */
QPushButton {{
    background: rgba(255,255,255,0.07); border: 1px solid {border};
    border-radius: {r}px; padding: 7px 14px; color: {text};
}}
QPushButton:hover {{ background: rgba(255,255,255,0.13); border-color: {accent}; }}
QPushButton:pressed {{ background: rgba(255,255,255,0.05); }}
QPushButton:disabled {{ color: rgba(255,255,255,0.35); border-color: rgba(255,255,255,0.08); }}
"""


def nav_pill_qss(accent="#4c8dff", text="#c9d1e2", radius=9) -> str:
    """顶部导航胶囊按钮：悬停浅底、选中强调色底 + 白字"""
    return f"""
QPushButton {{
    background: transparent; color: {text}; border: 1px solid transparent;
    padding: 5px 13px; font-size: 13px; font-family: "{M.font}";
    border-radius: {radius}px;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.12); color: white; }}
QPushButton:checked {{
    background: {accent}; color: white; border: 1px solid rgba(255,255,255,0.28);
}}
"""


def card_qss(surface="rgba(255,255,255,0.045)", border="#39405a", radius=None) -> str:
    """卡片容器风格（半透明面 + 1px 描边 + 圆角）"""
    r = int(radius if radius is not None else M.radius_card)
    return (f"QFrame {{ background: {surface}; border: 1px solid {border};"
            f" border-radius: {r}px; }}")


def section_title(text: str, accent="#4c8dff") -> QLabel:
    """区块标题：左侧强调色竖条 + 标题文字"""
    lbl = QLabel(f"<span style='color:{accent};'>▍</span> {text}")
    lbl.setStyleSheet(f"color: #e6eaf2; font-family: '{M.font}';"
                      f" font-size: 15px; font-weight: bold; padding: 2px 0;")
    return lbl


# ══════════════════════ 安装 ══════════════════════
_installed = False


def dark_palette(accent="#4c8dff"):
    """深色调色板：只设 QSS 是不够的 —— QScrollArea 视口、自动填充背景的控件
    会用「调色板 Window 色」自绘，不换调色板就会在深色界面里露出白块。"""
    from PyQt5.QtGui import QPalette
    p = QPalette()
    bg, surface, base = QColor("#161a24"), QColor("#20263a"), QColor("#1a1f2e")
    text, dim = QColor("#e6eaf2"), QColor("#a9b2c6")
    acc = QColor(accent)
    p.setColor(QPalette.Window, bg)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, surface)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, surface)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, surface)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Highlight, acc)
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, acc)
    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#6d7688"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#6d7688"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#6d7688"))
    try:
        p.setColor(QPalette.PlaceholderText, dim)
    except Exception:
        pass
    return p


def install(app: QApplication = None, accent="#4c8dff"):
    """安装全局 QSS + 深色调色板（幂等）。应在创建主窗口前调用。"""
    global _installed
    try:
        app = app or QApplication.instance()
        if app is None:
            return False
        app.setStyle("Fusion")                 # Fusion 才能完整套用调色板
        app.setPalette(dark_palette(accent))
        # ⚠ 全局 QSS 的文字色必须**取当前色板**，不能用 silicon_qss 里写死的默认值
        #   （#e6eaf2 / #a9b2c6）：样式表优先级高于调色板，写死就等于「主题与自定义
        #   文字色永远被盖住」—— 用户报的"文字颜色没生效"根因就是这个。
        try:
            from . import colors as _C
            app.setStyleSheet(silicon_qss(
                accent=accent,
                text=_C.Color1.name(),
                text_dim=_C.Gray2.name(),
                surface=_C.Color6.name(),
                surface2=_C.Color7.name(),
                bg=_C.Color8.name(),
                border=_C.Color5.name()))
        except Exception as _e:
            print(f"[SiliconUI] ⚠ 取色板文字色失败（用默认）: {_e}")
            app.setStyleSheet(silicon_qss(accent=accent))
        app.setFont(QFont(M.font, M.font_size))
        _installed = True
        print("[SiliconUI] 新界面样式已加载（亚克力 / 圆角 / 调色板 / 强调色 / 文字色跟随色板）")
        return True
    except Exception as e:
        print(f"[SiliconUI] 样式安装失败: {e}")
        return False


# ══════════════════════ 左侧竖向导航栏（SiliconUI 布局）══════════════════════
from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy  # noqa: E402
from PyQt5.QtCore import pyqtSignal  # noqa: E402


class PCLNavRail(QFrame):
    """左侧竖向导航栏：每项 = 图标 + 文字，选中项为强调色胶囊 + 左侧高亮条。

    与顶部横排导航的区别：左侧竖栏更接近 Fluent/Silicon 的桌面应用布局，
    内容区更宽、层级更清晰。
    """

    nav_changed = pyqtSignal(int)     # 页面索引

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self._items = items or []     # [(label, icon_path, page_index)]
        self._buttons = []
        self.setFixedWidth(96)
        self.setStyleSheet("PCLNavRail { background: transparent; border: none; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)
        for label, icon_path, idx in self._items:
            btn = QPushButton(f"  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(46)
            try:
                from PyQt5.QtGui import QIcon, QPixmap
                if icon_path:
                    btn.setIcon(QIcon(icon_path))
                    btn.setIconSize(QPixmap(icon_path).scaled(20, 20).size())
            except Exception:
                pass
            btn.clicked.connect(lambda checked=False, i=idx: self._on_click(i))
            lay.addWidget(btn)
            self._buttons.append((idx, btn))
        lay.addStretch()
        self._accent = "#4c8dff"
        self.set_active(0)

    def set_accent(self, accent_hex: str):
        self._accent = accent_hex or self._accent
        self.set_active(self._active)

    def _on_click(self, idx):
        self.set_active(idx)
        self.nav_changed.emit(idx)

    def set_active(self, idx):
        self._active = idx
        a = self._accent
        for i, btn in self._buttons:
            btn.setChecked(i == idx)
            on = (i == idx)
            btn.setStyleSheet(f"""
QPushButton {{
    background: {'rgba(255,255,255,0.06)' if not on else a};
    color: {'#c9d1e2' if not on else '#ffffff'};
    border: none; border-left: 3px solid {'transparent' if not on else '#ffffff'};
    border-radius: 10px; text-align: left; padding-left: 10px;
    font-family: "{M.font}"; font-size: 13px;
}}
QPushButton:hover {{ background: {'rgba(255,255,255,0.12)' if not on else a}; color: #ffffff; }}
""")


# ══════════════════════ 启用勾选（√）样式 ══════════════════════
_check_png_cache = {}


def _check_png(color="#ffffff") -> str:
    """生成一张带透明背景的对勾 PNG（QSS 里用 image: url(...)）"""
    if color in _check_png_cache and os.path.exists(_check_png_cache[color]):
        return _check_png_cache[color]
    try:
        from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
        from PyQt5.QtCore import Qt, QPointF
        pm = QPixmap(18, 18)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(2.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(QPointF(4, 9.5), QPointF(7.5, 13), QPointF(14, 5.5))
        p.end()
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp")
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "silicon_check.png")
        pm.save(f, "PNG")
        _check_png_cache[color] = f
        return f
    except Exception:
        return ""


def enabled_check_qss(text_color="#e6eaf2", accent=None) -> str:
    """插件「启用」开关：未选中=空心圆角框，选中=强调色描边 + √ 号（不再用蓝色填充）"""
    acc = accent or accent_hex_static()
    img = _check_png("#ffffff")
    img_qss = f"image: url({img.replace(os.sep, '/')});" if img else ""
    return f"""
QCheckBox {{ color: {text_color}; font-size: 13px; spacing: 8px; }}
QCheckBox::indicator {{
    width: 20px; height: 20px; border-radius: 6px;
    border: 1.6px solid rgba(255,255,255,0.35); background: rgba(255,255,255,0.04);
}}
QCheckBox::indicator:hover {{ border-color: {acc}; }}
QCheckBox::indicator:checked {{
    border: 1.6px solid {acc}; background: transparent; {img_qss}
}}
"""


def accent_hex_static() -> str:
    try:
        from .colors import ACCENT_ID, THEME_COLORS
        return THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")
    except Exception:
        return "#2f6fd0"


def enable_shared_gl_contexts() -> bool:
    """**必须在 QApplication 创建之前调用**：让所有 QOpenGLWidget 共享 GL 上下文。

    为什么必须有它（用户报的"Live2D 画布频闪 / 预览窗口崩坏"的真正根因）：
      Cubism 原生引擎是**进程级全局单例**，而 `LAppModel` 的 GL 资源（着色器/纹理）
      绑在**第一个**建立起来的 GL 上下文上。启动器里可能同时存在三个 Live2D 画布：
        ① 立绘工坊里那块内嵌预览（角色没有 2D 素材时会显示 Live2D）
        ② 「打开实时预览窗口」的独立窗口
        ③ 动作/表情调试器的画布
      不共享上下文时，第 2、3 个画布在自己的上下文里画不出东西 → 实测帧缓冲里
      **模型墨迹 0.0%、帧间跳变 0.0%**（完全空白/冻结），用户看到的就是"崩坏 / 频闪"
      （_audit_fish9269/probe_l2d_two_canvases.py 三种画布同时开的实测）。
      打开 Qt 的共享上下文开关后，三个画布各自 40.3% / 39.8% / 29.1% 墨迹、都在动。

    ⚠ 只能在 QApplication 构造前设置（Qt 的硬性要求，晚设置无效且会打警告），
      所以启动入口（silicon_window.launch / debug_live2d.py）在创建 app 前调它。
    """
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
        return True
    except Exception as e:
        print(f"[SiliconUI] ⚠ 共享 GL 上下文开关失败（多个 Live2D 画布可能画不出来）: {e}")
        return False
