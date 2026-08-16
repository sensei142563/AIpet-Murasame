"""PCL 风格颜色系统 + 主题色 + 图标路径"""

from PyQt5.QtGui import QColor
import os

# ===== 基础色板 (PCL 蓝) =====
Color1 = QColor(0x34, 0x3d, 0x4a)  # 深蓝灰 — 文字主色
Color2 = QColor(0x0b, 0x5b, 0xcb)  # 深蓝
Color3 = QColor(0x13, 0x70, 0xf3)  # 标准蓝 — 选中/激活色
Color4 = QColor(0x48, 0x90, 0xf5)  # 中蓝 — hover 色
Color5 = QColor(0x96, 0xc0, 0xf9)  # 浅蓝
Color6 = QColor(0xd5, 0xe6, 0xfd)  # 极浅蓝
Color7 = QColor(0xe0, 0xea, 0xfd)  # 更浅蓝
Color8 = QColor(0xea, 0xf2, 0xfe)  # 最浅蓝 — 背景色

# ===== 灰色系 =====
Gray1 = QColor(0x40, 0x40, 0x40)
Gray2 = QColor(0x60, 0x60, 0x60)
Gray3 = QColor(0x80, 0x80, 0x80)
Gray4 = QColor(0xa0, 0xa0, 0xa0)
Gray5 = QColor(0xc0, 0xc0, 0xc0)
Gray6 = QColor(0xe0, 0xe0, 0xe0)
Gray7 = QColor(0xf0, 0xf0, 0xf0)
Gray8 = QColor(0xf5, 0xf5, 0xf5)

# ===== 红色系 =====
RedBack = QColor(0xfb, 0xdd, 0xdd, 0x80)  # 半透明红底
RedLight = QColor(0xff, 0x4c, 0x4c)
RedDark = QColor(0xce, 0x21, 0x11)

# ===== 绿色 =====
GreenLight = QColor(0x4c, 0xdd, 0x4c)
GreenDark = QColor(0x21, 0xaa, 0x11)

# ===== 5 套主题色 =====
THEME_COLORS = {
    "blue": {
        "title_start": "#1370f3",
        "title_end": "#4890f5",
        "btn_start": "#4890f5",
        "btn_end": "#1370f3",
        "sidebar_bg": QColor(241, 255, 255, 242),  # rgba(241,255,255,0.95)
    },
    "red": {
        "title_start": "#e03030",
        "title_end": "#f06060",
        "btn_start": "#f06060",
        "btn_end": "#e03030",
        "sidebar_bg": QColor(255, 241, 241, 242),
    },
    "green": {
        "title_start": "#30a030",
        "title_end": "#60c060",
        "btn_start": "#60c060",
        "btn_end": "#30a030",
        "sidebar_bg": QColor(241, 255, 241, 242),
    },
    "gold": {
        "title_start": "#d4a020",
        "title_end": "#e8c040",
        "btn_start": "#e8c040",
        "btn_end": "#d4a020",
        "sidebar_bg": QColor(255, 251, 240, 242),
    },
    "dark": {
        "title_start": "#404040",
        "title_end": "#606060",
        "btn_start": "#606060",
        "btn_end": "#404040",
        "sidebar_bg": QColor(240, 240, 240, 242),
    },
}

# ===== 图标路径（相对于 pcl_launcher 目录） =====
_RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "blocks")


def block_icon(name: str) -> str:
    return os.path.join(_RESOURCES, f"{name}.png")


# ===== 缩放系数 =====
S = 1.0  # 基础缩放（可根据屏幕调整）