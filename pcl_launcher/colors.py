# -*- coding: utf-8 -*-
"""PCL 颜色系统 + 主题加载 + 图标路径

主题机制：
- themes/<id>/theme.json 定义一套完整色板（含全部 Color*/Gray*/Red*/Green*/preview_bg/accent）
- 启动时按 config.json 的 ui_theme（默认 classic）加载色板，缺省字段回退内置经典值
- THEME_COLORS 提供 6 套强调色（blue/red/green/gold/dark/crimson），可随时切换
- 控件在构建时读取本模块颜色对象 → 切换主题时用 apply_theme_live() 原地改值 +
  重建外壳/页面样式，**无需重启启动器**（apply_accent_live() 同理切换强调色）
"""

from PyQt5.QtGui import QColor
import os
import sys
import json

# ===== 内置经典色板（回退基准 = 旧版主题）=====
_DEFAULT = {
    "Color1": "#343d4a", "Color2": "#0b5bcb", "Color3": "#1370f3",
    "Color4": "#4890f5", "Color5": "#96c0f9", "Color6": "#d5e6fd",
    "Color7": "#e0eafd", "Color8": "#eaf2fe",
    "Gray1": "#404040", "Gray2": "#606060", "Gray3": "#808080",
    "Gray4": "#a0a0a0", "Gray5": "#c0c0c0", "Gray6": "#e0e0e0",
    "Gray7": "#f0f0f0", "Gray8": "#f5f5f5",
    "RedBack": "#80fbdddd", "RedLight": "#ff4c4c", "RedDark": "#ce2111",
    "GreenLight": "#4cdd4c", "GreenDark": "#21aa11",
    "preview_bg": "#eaf2fe",
    "accent": "blue",
}


def _app_base_dir() -> str:
    """程序根目录：frozen 用 exe 目录；源码用项目根"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config() -> dict:
    try:
        with open(os.path.join(_app_base_dir(), "config.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _resolve_theme_dir() -> str:
    """主题目录：
    - 源码模式：pcl_launcher/themes
    - frozen：优先 exe 旁 pcl_launcher/themes（绿色版带源码，可持久导入/导出自定义主题）；
      不存在则回退打包进 _internal 的 themes（只读兜底）"""
    if getattr(sys, "frozen", False):
        side = os.path.join(os.path.dirname(sys.executable), "pcl_launcher", "themes")
        if os.path.isdir(side):
            return side
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")


THEME_DIR = _resolve_theme_dir()

# 内存里"当前真正在用的主题"：apply_theme_live() 换肤时写，current_theme_id() 优先用它。
# 空串 = 还没换过肤（启动阶段）→ 回退读 config.json 的 ui_theme。
_ACTIVE_THEME_ID = ""


def _list_themes():
    """扫描 themes/ 目录返回 [{"id","name","builtin","desc","accent"}...]（按目录名排序）"""
    out = []
    if not os.path.isdir(THEME_DIR):
        return out
    for tid in sorted(os.listdir(THEME_DIR)):
        pj = os.path.join(THEME_DIR, tid, "theme.json")
        if not os.path.isfile(pj):
            continue
        try:
            with open(pj, "r", encoding="utf-8") as f:
                meta = json.load(f)
            out.append({
                "id": meta.get("id", tid),
                "name": meta.get("name", tid),
                "desc": meta.get("desc", ""),
                "accent": meta.get("accent", "blue"),
                "builtin": bool(meta.get("builtin", True)),
                "_dir": os.path.join(THEME_DIR, tid),
            })
        except Exception:
            continue
    return out


def _load_theme_palette(theme_id: str) -> dict:
    """加载主题色板（未命中字段回退经典色）"""
    pal = dict(_DEFAULT)
    if theme_id:
        pj = os.path.join(THEME_DIR, str(theme_id), "theme.json")
        try:
            if os.path.isfile(pj):
                with open(pj, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in (data.get("colors") or {}).items():
                    pal[k] = v
                pal["accent"] = data.get("accent", pal.get("accent", "blue"))
        except Exception:
            pass
    return pal


def current_theme_id() -> str:
    """当前主题 id：**以内存里正在用的为准**，其次才看 config.json。

    为什么不能只读 config.json：换肤是"先改内存色板、config 稍后才落盘"（预览时
    甚至 persist=False 不落盘）。而主题背景/资源（background_info / theme_asset /
    nav_icon_path）都要按"当前主题"去查目录 —— 只看 config 就会拿到**上一个**主题的背景，
    于是切到没有背景的主题后，旧主题的视频还在继续播（用户报的"切了主题背景没变"）。
    """
    if _ACTIVE_THEME_ID and os.path.isdir(os.path.join(THEME_DIR, _ACTIVE_THEME_ID)):
        return _ACTIVE_THEME_ID
    cfg = _config()
    tid = str(cfg.get("ui_theme", "classic") or "classic").strip()
    # 主题目录不存在时回退经典
    if not os.path.isdir(os.path.join(THEME_DIR, tid)):
        return "classic"
    return tid


def _q(value):
    """hex 或 rgba() 文本 → QColor（失败回退灰）"""
    try:
        s = str(value).strip()
        if s.startswith("rgba("):
            s = s[5:-1]
            parts = [int(x.strip()) for x in s.split(",")]
            if len(parts) == 4:
                return QColor(parts[0], parts[1], parts[2], parts[3])
            if len(parts) == 3:
                return QColor(parts[0], parts[1], parts[2])
        return QColor(s)
    except Exception:
        return QColor("#808080")


def _derive_from_base(pal: dict) -> dict:
    """按「启动器底色」(config.ui_bg_color) 派生整套界面颜色。

    目的：用户改底色时，按钮旁边的白色区域（页面/面板/卡片/输入框底色）与
    所有文字颜色一起跟着变，并且自动保证对比度（底深→浅字，底浅→深字）。
    未设置 ui_bg_color 时原样返回（保持主题自带配色）。
    """
    try:
        import json as _json
        cfg_path = os.path.join(_app_base_dir(), "config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        base_hex = str(cfg.get("ui_bg_color") or "").strip()
        if not base_hex:
            return pal
        b = QColor(base_hex)
        if not b.isValid():
            return pal
        dark = b.lightness() < 140
        p2 = dict(pal)
        # 窗口底色 / 面板面（半透明，壁纸仍可透出）
        p2["Color8"] = f"rgba({b.red()},{b.green()},{b.blue()},215)"
        # 卡片、输入框、次级面：朝白/黑插值（纯黑用 lighter 是无效的 → 会看不出层次）
        def _mix(c: QColor, k: float) -> QColor:
            """k>0 往白里混，k<0 往黑里混"""
            if k >= 0:
                return QColor(int(c.red() + (255 - c.red()) * k),
                              int(c.green() + (255 - c.green()) * k),
                              int(c.blue() + (255 - c.blue()) * k))
            k = -k
            return QColor(int(c.red() * (1 - k)), int(c.green() * (1 - k)),
                          int(c.blue() * (1 - k)))
        if dark:
            face, face2, border = _mix(b, 0.10), _mix(b, 0.17), _mix(b, 0.30)
        else:
            face, face2, border = _mix(b, -0.05), _mix(b, -0.10), _mix(b, -0.20)
        p2["Color6"] = face.name()
        p2["Color7"] = face2.name()
        p2["Color5"] = border.name()
        # 文字：深底浅字 / 浅底深字
        p2["Color1"] = "#eef1f7" if dark else "#1f232b"
        p2["Gray1"] = "#ffffff" if dark else "#000000"
        p2["Gray2"] = "#b9c2d6" if dark else "#5a5f6b"
        p2["Gray3"] = "#98a2b8" if dark else "#6d7280"
        # 8 级灰阶是「文字 → 背景」的单调亮度阶梯（旧版主题就是这个梯度：
        # Gray1 #404040 一路到 Gray8 #f5f5f5）。自定义底色时必须**整条重算**——
        # 只算前三级会留下"主题自带的浅灰面 + 派生出来的浅色文字"这种自相矛盾的
        # 组合，表现就是浅字压浅面 = 看不清。千恋万花·樱华主题正是这样中枪的：
        # 它的 Gray6/7/8 是 #e2d5c7 / #f1e8dd / #f7f0e7 浅米色，而派生文字是
        # #eef1f7，于是"字看不清"。
        # 比例取旧版主题各级与底色的实际距离（Gray4 .37 / Gray5 .25 / Gray6 .12 /
        # Gray7 .06 / Gray8 .04）→ 浅底就是经典的 #a1a1a1/#bfbfbf/#e0e0e0/#f0f0f0/#f5f5f5，
        # 深底按同样幅度往白里混（对比度对称）。
        for _k, _name in ((0.37, "Gray4"), (0.25, "Gray5"), (0.12, "Gray6"),
                          (0.06, "Gray7"), (0.04, "Gray8")):
            p2[_name] = _mix(b, _k if dark else -_k).name()
        p2["preview_bg"] = (b.darker(120) if dark else b.lighter(104)).name()
        print(f"[Colors] 已按启动器底色派生界面配色: 底={base_hex}"
              f" 文字={'浅' if dark else '深'} 面={face.name()}")
        return p2
    except Exception as e:
        print(f"[Colors] ⚠ 底色派生失败（用主题配色）: {e}")
        return pal


# ===== 当前主题色板（启动时加载一次）=====
_PAL = _derive_from_base(_load_theme_palette(current_theme_id()))
ACCENT_ID = str(_PAL.get("accent", "blue"))

# ===== 基础色板 =====
Color1 = _q(_PAL["Color1"])   # 文字主色
Color2 = _q(_PAL["Color2"])
Color3 = _q(_PAL["Color3"])   # 选中/激活色
Color4 = _q(_PAL["Color4"])   # hover
Color5 = _q(_PAL["Color5"])
Color6 = _q(_PAL["Color6"])
Color7 = _q(_PAL["Color7"])
Color8 = _q(_PAL["Color8"])   # 背景色

# ===== 灰色系 =====
Gray1 = _q(_PAL["Gray1"])
Gray2 = _q(_PAL["Gray2"])
Gray3 = _q(_PAL["Gray3"])
Gray4 = _q(_PAL["Gray4"])
Gray5 = _q(_PAL["Gray5"])
Gray6 = _q(_PAL["Gray6"])
Gray7 = _q(_PAL["Gray7"])
Gray8 = _q(_PAL["Gray8"])

# ===== 红色系 =====
RedBack = _q(_PAL["RedBack"])
RedLight = _q(_PAL["RedLight"])
RedDark = _q(_PAL["RedDark"])

# ===== 绿色 =====
GreenLight = _q(_PAL["GreenLight"])
GreenDark = _q(_PAL["GreenDark"])

# ===== 预览区背景（Live2D 清屏 / 立绘底）=====
PREVIEW_BG = _q(_PAL.get("preview_bg", "#eaf2fe"))


def base_bg_color() -> QColor:
    """窗口/二级窗口的**底板**颜色（alpha 固定 255，底板要保证内容清晰）。

    · 用户自选了「启动器底色」(config.ui_bg_color) → 用它（此时整套配色也跟着派生）
    · 没选（空串 = 跟随主题，默认）→ 用当前主题自己的底色 Color8
      ⚠ 以前这里硬编码回退 "#000000"：经典/樱华是浅色主题、文字是深色，
        底板一黑文字就"消失"，所以必须回退到主题底色而不是黑。
    """
    try:
        _hexv = str(_config().get("ui_bg_color") or "").strip()
        c = QColor(_hexv) if _hexv else QColor(Color8)
        if not c.isValid():
            c = QColor(Color8)
        c.setAlpha(255)
        return c
    except Exception:
        c = QColor(Color8)
        c.setAlpha(255)
        return c


# ══════════════════ 可读性工具（救「深色 UI 里写死的浅色字」）══════════════════
# 老界面是深色底 + 写死的浅色字（#e8e8f0 标题 / #9a9aa8 提示 / #888 说明 / #8fd18f 状态）。
# 主题系统支持浅色主题（经典 / 千恋万花）后，这些浅字压在浅底上就看不清了
# （用户报的「立绘工坊以及其连带的东西好多都出现了看不清字的阴间配色」）。
# 这里不写死替换色，而是**按当前主题底板算对比度**，浅底自动压暗、深底自动提亮，
# 用户自选「启动器底色」(ui_bg_color) 时也跟着对。
def rel_luminance(c) -> float:
    """WCAG 相对亮度"""
    def _f(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * _f(c.red()) + 0.7152 * _f(c.green()) + 0.0722 * _f(c.blue())


def contrast_ratio(a, b) -> float:
    """两色对比度（WCAG，1.0~21.0；正文建议 ≥ 4.5）"""
    la, lb = rel_luminance(a), rel_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(color, bg=None, target: float = 4.5):
    """把 color 沿明暗调到在当前主题底板上达到 target 对比度。

    bg 默认取「窗口底板色」base_bg_color()。已经够清楚就原样返回（不改变设计色）。

    ⚠ 方向判据是"**朝远离底色的方向调**"（文字比底暗就继续压暗，比底亮就提亮），
      不能用"底色亮度 < 0.5 就算深色"这种阈值判断：中灰底（如 #b3b9c2，亮度 0.46）
      会被误判成深色底 → 于是把灰字**提亮成白色**压在浅灰上（实测 1.97:1，比不改还糟）。
      这个坑是本函数的自测（test_contrast_fills.py）当场抓出来的。
    """
    c = QColor(color)
    b = QColor(bg) if bg is not None else base_bg_color()
    if contrast_ratio(c, b) >= target:
        return c
    toward_black = rel_luminance(c) < rel_luminance(b)
    out = QColor(c)
    for _ in range(60):
        out = out.darker(110) if toward_black else out.lighter(110)
        if contrast_ratio(out, b) >= target:
            return out
    return QColor("#000000") if toward_black else QColor("#ffffff")


def ok_text():
    """成功 / 已生效的状态字（跟着主题自动压暗或提亮）"""
    return readable_on(GreenDark)


def warn_text():
    """警告 / 失败的状态字"""
    return readable_on(RedDark)


# 「正向动作」的语义绿（**固定色，不跟主题走**）。
# 为什么固定：项目里红=危险、紫=创作 早就是固定色（#e03030 / #7a5cd8），绿却跟着主题走 ——
#   主题自带的绿配白字只有 3.08:1（#21aa11），而"压暗到够亮"会把色相退化成橄榄灰
#   （实测 senrenbanka 压完是 #5f874e，HLS 饱和度 0.27，看起来已经不是绿色了）。
#   固定成这个值：白字 5.4:1、HLS 饱和度 0.60（明确是绿），四个主题下语义一致。
ACTION_GREEN = QColor("#1e7a33")


def fill_for_text(fill, text="#ffffff", target: float = 4.8):
    """**填色 + 固定文字** 这类配对的保险：把填色压暗/提亮到与文字达到 target。

    为什么需要它（用户报的"彩色徽章白字看不清"，实测）：
      · 琥珀徽章 `#d4a020` + 白字 = **2.37:1**
      · 绿徽章   `#30a030` + 白字 = **3.39:1**
      · 绿按钮   `#21aa11` + 白字 = **3.08:1** ／ 备份按钮 `#2f8f4e` = 4.07:1
      · 深色主题的强调色当按钮底 `#4c8dff` + 白字 = **3.20:1**（它当文字/描边时是够的，当底不够）
    这类"底"必须自己保证对比度，不能指望主题色恰好够深。

    target 默认 4.8（留一点余量：实际渲染还会叠加 6% 白膜，实测会把底色抬亮 ~0.2:1）。
    """
    f = QColor(fill)
    t = QColor(text)
    if contrast_ratio(f, t) >= target:
        return f
    # 文字亮 → 底要压暗；文字暗 → 底要提亮
    toward_black = rel_luminance(t) > 0.5
    out = QColor(f)
    for _ in range(60):
        out = out.darker(110) if toward_black else out.lighter(110)
        if contrast_ratio(out, t) >= target:
            return out
    return QColor("#000000") if toward_black else QColor("#ffffff")


def blend_over(fg, alpha_0_255, bg) -> QColor:
    """把 fg 以 alpha（0–255）叠在 bg 上，返回**合成后的实色**。

    用途：半透明胶囊/卡片上的文字要不要换色，得先知道合成出来到底是什么颜色
    （例：`rgba(Color3, 60)` 压在浅底上合成 #4b92f5，配 Color1 文字只有 3.5:1）。
    """
    a = max(0, min(255, int(alpha_0_255))) / 255.0
    f, b = QColor(fg), QColor(bg)
    return QColor(int(f.red() * a + b.red() * (1 - a) + 0.5),
                  int(f.green() * a + b.green() * (1 - a) + 0.5),
                  int(f.blue() * a + b.blue() * (1 - a) + 0.5))


# 启动器窗口底不是单纯的主题色：是「渐变底板 + 6% 蒙版/磨砂」，
# 浅色主题实测顶部会到 #b3b9c2 这种中灰（探针无壁纸时的最坏情况）。
# 所以"次级文字"不能直接用 Gray2 压在上面（实测 3.18:1）——统一按最坏底色压暗一次。
_FILM_WORST_BG = QColor("#b3b9c2")


def secondary_text() -> QColor:
    """次级/提示文字的**可读**版本（浅色主题下会自动比 Gray2 更深）。

    深色主题里 Gray2 本来就够（实测 6.6:1+）→ 原样返回，观感不变。
    """
    try:
        if rel_luminance(QColor(Color8)) < 0.25:      # 深色主题：Gray2 已经够亮
            return QColor(Gray2)
        return readable_on(Gray2, _FILM_WORST_BG, 4.5)
    except Exception:
        return QColor(Gray2)


# 浅色主题里"卡片/药丸/说明条"那层乳白膜（surface_fill(120..190)）压在渐变底板上，
# 实测合成在 #cfd7e4 ~ #d6dde8。强调色当**文字**压在这层上只有 3.2~4.4:1（实测主题页
# 「旧版主题 ✅ 当前使用」3.24、「🔑 基础信息与密钥」4.40），所以单独给一个可读版本。
_FILM_LIGHT_BG = QColor("#cfd7e4")


def accent_text() -> QColor:
    """强调色当**文字**用时的可读版本（浅色主题下自动压深；深色主题保持鲜亮）。"""
    try:
        if rel_luminance(QColor(Color8)) < 0.25:      # 深色主题：强调色本来就鲜亮够用
            return QColor(Color3)
        return readable_on(Color3, _FILM_LIGHT_BG, 4.5)
    except Exception:
        return QColor(Color3)


def surface_fill(light_alpha: int = 150, dark_alpha: int = 22) -> str:
    """「磨砂面板 / 卡片」的填充色（CSS 片段，可直接塞进 QSS）。

    浅色主题：乳白半透明（透出壁纸，老界面的观感）；
    深色主题：极淡白膜（跟 `silicon_qss` 里 `rgba(255,255,255,0.03~0.06)` 一个路子）。

    ⚠ 老代码把这一层写死成 `rgba(255,255,255,150)`：在**深色主题**下它等于往深底上
      盖一层 59% 的白 → 合成出中灰板（实测插件页卡片 #9e9fa4），而卡片文字跟主题走
      是**浅色**的 → 1.2:1，等于看不见（用户报的"插件页卡片看不清"）。
    """
    try:
        if rel_luminance(QColor(Color8)) < 0.25:      # 深色主题
            return f"rgba(255,255,255,{int(dark_alpha)})"
    except Exception:
        pass
    return f"rgba(255,255,255,{int(light_alpha)})"


# ===== 6 套强调色（accent）=====
THEME_COLORS = {
    "blue": {
        # Silicon 现代蓝（新界面主色）：深→亮渐变，胶囊/高亮统一用它
        "title_start": "#2f6fd0", "title_end": "#4c8dff",
        "btn_start": "#4c8dff", "btn_end": "#2f6fd0",
        "sidebar_bg": QColor(241, 255, 255, 242),
    },
    "red": {
        "title_start": "#e03030", "title_end": "#f06060",
        "btn_start": "#f06060", "btn_end": "#e03030",
        "sidebar_bg": QColor(255, 241, 241, 242),
    },
    "green": {
        "title_start": "#30a030", "title_end": "#60c060",
        "btn_start": "#60c060", "btn_end": "#30a030",
        "sidebar_bg": QColor(241, 255, 241, 242),
    },
    "gold": {
        "title_start": "#d4a020", "title_end": "#e8c040",
        "btn_start": "#e8c040", "btn_end": "#d4a020",
        "sidebar_bg": QColor(255, 251, 240, 242),
    },
    "dark": {
        "title_start": "#404040", "title_end": "#606060",
        "btn_start": "#606060", "btn_end": "#404040",
        "sidebar_bg": QColor(240, 240, 240, 242),
    },
    "crimson": {
        "title_start": "#8e2b3a", "title_end": "#c05a68",
        "btn_start": "#c05a68", "btn_end": "#8e2b3a",
        "sidebar_bg": QColor(253, 240, 235, 242),
    },
}

# ===== 主题资源与控件风格（供页面/按钮渲染） =====
def _current_theme_dir() -> str:
    return os.path.join(THEME_DIR, current_theme_id())


def _theme_json() -> dict:
    try:
        with open(os.path.join(_current_theme_dir(), "theme.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def theme_asset(rel: str) -> str:
    """返回当前主题目录内资源文件路径；不存在返回空串（调用方自行跳过）"""
    if not rel:
        return ""
    p = os.path.join(_current_theme_dir(), str(rel).replace("/", os.sep))
    return p if os.path.isfile(p) else ""


def nav_icon_path(key: str) -> str:
    """导航按钮图（主题 nav_icons.<key>，如 model/settings）；无则空串"""
    return theme_asset((_theme_json().get("nav_icons") or {}).get(key, ""))


def background_info():
    """主题背景声明：返回 (type, path, opacity)。type 为 'image'/'video'/''"""
    try:
        bg = (_theme_json().get("background") or {}) or {}
        btype = str(bg.get("type", "")).strip().lower()
        src = theme_asset(str(bg.get("source", "") or ""))
        try:
            opacity = float(bg.get("opacity", 1.0))
        except Exception:
            opacity = 1.0
        if src and btype in ("image", "video"):
            return btype, src, max(0.0, min(1.0, opacity))
    except Exception:
        pass
    return "", "", 1.0


def btn_radius() -> int:
    """主题按钮圆角（卡通化用）"""
    try:
        return int((_theme_json().get("widgets") or {}).get("btn_radius", 8))
    except Exception:
        return 8


def primary_btn_qss(pad_v: int = 8, pad_h: int = 18, font_size: int = 13,
                    radius: int = None, gradient: bool = True) -> str:
    """统一卡通化主按钮 QSS：主题色渐变 + 高光 + 大圆角 + 白描边"""
    r = radius if radius is not None else btn_radius()
    if gradient:
        bg = (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,"
              f"stop:0 {Color4.name()},stop:1 {Color3.name()})")
    else:
        bg = Color3.name()
    return f"""
        QPushButton {{ background: {bg}; color: white; border: 2px solid rgba(255,255,255,0.45);
            padding: {pad_v}px {pad_h}px; font-size: {font_size}px; font-weight: bold;
            font-family: 'Microsoft YaHei'; border-radius: {r}px; }}
        QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.9);
            background: {Color4.name()}; }}
        QPushButton:pressed {{ background: {Color2.name()}; }}
        QPushButton:disabled {{ color: rgba(255,255,255,0.6); border-color: rgba(255,255,255,0.15); }}
    """


# ===== 缩放系数 =====
S = 1.0  # 基础缩放（可根据屏幕调整）


# ══════════════════ 运行时换肤（切换主题/强调色无需重启启动器）══════════════════
# 各界面模块都是 `from .colors import *`：拿到的是**同一批 QColor 对象**。
# 所以原地 setRgba 改值 → 所有持有者（含 SF()/PREVIEW_BG/按钮渐变）立刻看到新颜色；
# 已经生成的 QSS 字符串由调用方重建控件刷新（外壳重设样式 + 当前页面重建）。
_RUNTIME_KEYS = (
    "Color1", "Color2", "Color3", "Color4", "Color5", "Color6", "Color7", "Color8",
    "Gray1", "Gray2", "Gray3", "Gray4", "Gray5", "Gray6", "Gray7", "Gray8",
    "RedBack", "RedLight", "RedDark", "GreenLight", "GreenDark", "PREVIEW_BG",
)


def _apply_palette_inplace(pal: dict) -> None:
    """把新色板写进已存在的颜色对象（原地改值，不换对象 → 全局生效）"""
    g = globals()
    for key in _RUNTIME_KEYS:
        if key not in pal:
            continue
        obj = g.get(key)
        if not isinstance(obj, QColor):
            continue
        try:
            obj.setRgba(_q(pal[key]).rgba())
        except Exception:
            pass


def accent_hex(accent_key: str = None) -> str:
    """强调色主色（accent_key 为空时用当前强调色）"""
    key = str(accent_key or ACCENT_ID or "blue")
    return str(THEME_COLORS.get(key, {}).get("title_start", "#4c8dff"))


def apply_theme_live(theme_id: str) -> dict:
    """实时切换主题（不重启启动器）：重载色板 → 按启动器底色派生 → 原地更新颜色对象。

    返回新色板（含 accent）。调用方随后重建外壳样式与当前页面。
    """
    global _PAL, ACCENT_ID, _ACTIVE_THEME_ID
    theme_id = str(theme_id or "").strip() or "silicon"
    if not os.path.isdir(os.path.join(THEME_DIR, theme_id)):
        theme_id = "classic"
    pal = _derive_from_base(_load_theme_palette(theme_id))
    _apply_palette_inplace(pal)
    _PAL = pal
    ACCENT_ID = str(pal.get("accent", "blue") or "blue")
    _ACTIVE_THEME_ID = theme_id        # 背景/图标资源都要按这个主题查目录
    print(f"[Colors] 主题已实时切换 → {theme_id}（强调色 {ACCENT_ID}）")
    return pal


def apply_accent_live(accent_key: str) -> str:
    """实时切换强调色（主题色）：更新 _PAL/ACCENT_ID，并写回当前主题的 theme.json。"""
    global ACCENT_ID
    key = str(accent_key or "").strip()
    if key not in THEME_COLORS:
        return accent_hex()
    ACCENT_ID = key
    try:
        _PAL["accent"] = key
    except Exception:
        pass
    try:
        pj = os.path.join(_current_theme_dir(), "theme.json")
        if os.path.isfile(pj):
            with open(pj, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["accent"] = key
            tmp = pj + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, pj)
    except Exception as e:
        print(f"[Colors] ⚠ 强调色写回主题失败: {e}")
    print(f"[Colors] 强调色已实时切换 → {key} ({accent_hex(key)})")
    return accent_hex(key)
