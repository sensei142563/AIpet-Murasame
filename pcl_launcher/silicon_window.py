# -*- coding: utf-8 -*-
"""AIpet 启动器 · Silicon 新版外壳（左侧导航栏 + 卡片内容区，Fluent 风格）。

设计参考 PyQt-SiliconUI 那一类界面语言：
- 无边框 + 亚克力模糊 + 圆角 + 强调色（silicon_ui 提供）
- 左侧竖向导航栏（图标 + 文字，选中项强调色高亮 + 左侧指示条）
- 右侧内容区：卡片式页面，页面之间用 QStackedWidget 切换
- 顶部自定义标题栏（应用名 + 运行状态点 + 最小化/关闭）

功能对齐旧版启动器（全部保留）：
总览（启动桌宠/QQ/微信 + 控制面板 + 状态）、桌宠管理（卡片/活动/立绘工坊/设置/新建/删除）、
设置、记忆、提示词、插件、主题；主题壁纸/背景视频、强调色、NapCat 工具、更新日志、
打开配置/目录、关窗清理子进程。
"""
import os
import re
import subprocess
import sys
import urllib.request

from PyQt5.QtCore import Qt, QTimer, QEvent, QSize, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QIcon, QImage, QPainter, QPainterPath,
                         QPixmap)
from PyQt5.QtWidgets import (QScrollArea, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QFrame, QMessageBox, QSizePolicy,
                             QGraphicsOpacityEffect, QScrollArea)

from .colors import *          # noqa: F401,F403  (Color1..8 / Gray* / S / THEME_COLORS / btn_radius …)
from . import silicon_ui
from .colors import (ACCENT_ID, THEME_COLORS, background_info, btn_radius)

_CONTROL_BASE = "http://localhost:28565/control"

# 导航项（key, 图标, 标题, 副标题）
NAV = [
    ("home",    "", "总览",  "启动与状态"),
    ("pets",    "", "桌宠",  "角色与立绘"),
    ("memory",  "", "记忆",  "对话与备份"),
    ("prompt",  "", "提示词", "人设微调"),
    ("plugins", "", "插件",  "功能开关"),
    ("themes",  "", "主题",  "外观与配色"),
]


def _is_light_theme() -> bool:
    """当前主题底色是浅色？（千恋万花=浅色，silicon=深色）"""
    try:
        return Color8.lightness() > 140
    except Exception:
        return False


def SF(alpha: float) -> str:
    """半透明面颜色：深色主题=白透明，浅色主题=黑透明（两边都能看出卡片层次）"""
    if _is_light_theme():
        return f"rgba(0,0,0,{max(0.02, min(0.30, alpha)):.3f})"
    return f"rgba(255,255,255,{max(0.02, min(0.30, alpha)):.3f})"


def _app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_src_on_path():
    """把程序目录加入 sys.path（冻结版兜底）。

    外壳的页面是「字符串动态导入」懒加载的，PyInstaller 静态分析看不到 →
    万一某个模块没被打进 exe，这里就能用随包的源码导入，而不是整页「加载失败」。
    （打包时已用 --hidden-import 显式声明；这里是第二道保险。）"""
    try:
        base = _app_base_dir()
        if base and base not in sys.path and os.path.isdir(os.path.join(base, "pcl_launcher")):
            sys.path.insert(0, base)
            print(f"[NewUI] 已把程序目录加入导入路径: {base}")
            return True
    except Exception as e:
        print(f"[NewUI]  程序目录加入导入路径失败: {e}")
    return False


def _quiet_mode() -> bool:
    """纯净模式（设置 → 其他配置）：启动桌宠 / QQ / 微信时不弹终端窗口"""
    try:
        import json as _j
        with open(os.path.join(_app_base_dir(), "config.json"), encoding="utf-8") as f:
            return str(_j.load(f).get("quiet_mode", "false")).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def _spawn_flags() -> int:
    """子进程窗口标志：纯净模式 = CREATE_NO_WINDOW，否则开新控制台（方便看日志）"""
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if _quiet_mode()         else subprocess.CREATE_NEW_CONSOLE


class _VideoBgPlayer(QThread):
    """视频背景播放器：用 OpenCV 逐帧解码 → 交给底板当壁纸画。

    ★ 为什么不用 QMediaPlayer：这台机器上 Qt 的多媒体后端（wmfengine/dsengine）
      打不开**完全标准**的 H.264 1080p mp4（实测 error=1 ResourceError、
      mediaStatus=InvalidMedia，isAvailable 也是 False/无有效 service），
      视频背景就永远不显示（用户反馈）。cv2 自己解码不依赖系统解码器，最可靠，
      还顺带解决了「中文路径」和「透明窗口装不下原生视频表面」两个坑。
    """
    frame_ready = pyqtSignal(object)      # QImage

    def __init__(self, path: str, fps_cap: float = 12.0, parent=None):
        super().__init__(parent)
        self._path = str(path)
        self._fps_cap = max(1.0, float(fps_cap))
        self._stop = False
        # ★ 背景透明度/模糊度也要作用在视频上（用户反馈：滑块对视频背景无效）。
        #   图片壁纸是把透明度"烘进画面"再当壁纸的，视频以前直接原帧贴上去 → 滑块没反应。
        self._opacity = 1.0
        self._blur = 0

    def set_effects(self, opacity=None, blur=None):
        """实时更新透明度/模糊（滑块拖动时调用；下一帧就生效，不用重启播放）"""
        try:
            if opacity is not None:
                self._opacity = max(0.05, min(1.0, float(opacity)))
            if blur is not None:
                self._blur = max(0, int(blur))
        except Exception:
            pass

    def stop(self):
        self._stop = True
        try:
            self.requestInterruption()
        except Exception:
            pass

    def run(self):
        try:
            import cv2
            from PyQt5.QtGui import QImage
        except Exception as e:
            print(f"[NewUI] ⚠ 视频背景需要 cv2（不可用: {e}）")
            return
        cap = None
        try:
            cap = cv2.VideoCapture(self._path)
            if not cap or not cap.isOpened():
                print(f"[NewUI] ⚠ 打不开背景视频: {self._path}")
                return
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            step = max(1, int(round(src_fps / self._fps_cap)))   # 抽帧到 ~12fps，省 CPU
            idx = 0
            t_next = 0.0
            import time as _t
            while not self._stop and not self.isInterruptionRequested():
                ok, frame = cap.read()
                if not ok:                     # 播完 → 从头循环
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    idx = 0
                    continue
                idx += 1
                if idx % step:
                    continue
                try:
                    # 模糊（在解码线程里做，不吃界面线程）
                    _b = int(getattr(self, "_blur", 0) or 0)
                    if _b > 0:
                        k = max(3, int(_b) * 2 + 1)
                        frame = cv2.GaussianBlur(frame, (k, k), 0)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
                    # ★ 透明度：烘进画面（和图片壁纸同一套做法），否则滑块对视频无效
                    _op = float(getattr(self, "_opacity", 1.0) or 1.0)
                    if _op < 0.995:
                        from PyQt5.QtGui import QPainter as _QP
                        from PyQt5.QtCore import Qt as _Qt2
                        faded = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
                        faded.fill(_Qt2.transparent)
                        _p = _QP(faded)
                        if _p.isActive():
                            _p.setOpacity(max(0.05, min(1.0, _op)))
                            _p.drawImage(0, 0, img)
                            _p.end()
                        img = faded
                    self.frame_ready.emit(img)
                except Exception:
                    pass
                # 按抽帧后的节奏限速
                t_next += 1.0 / self._fps_cap
                dt = t_next - _t.time()
                if dt > 0:
                    _t.sleep(min(0.5, dt))
                else:
                    t_next = _t.time()
        except Exception as e:
            print(f"[NewUI] ⚠ 视频背景播放异常: {e}")
        finally:
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass


def _ascii_media_path(src: str) -> str:
    """给媒体播放器一个「纯 ASCII 路径」。

    ★ Windows 的 DirectShow/WMF 后端**打不开含中文的路径**（错误码 1 ResourceError、
      mediaStatus=InvalidMedia），表现就是"视频背景永远不显示"（用户反馈；本项目路径
      是 D:\下载\AI桌宠\…）。先用 8.3 短路径，取不到就复制到纯 ASCII 缓存目录。
    """
    try:
        src = os.path.abspath(src)
        if not os.path.isfile(src):
            return src
        if src.isascii():
            return src
        # ① 8.3 短路径（不复制文件，最省事）
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(src, buf, 1024) and buf.value:
                if str(buf.value).isascii() and os.path.isfile(buf.value):
                    print(f"[NewUI] 背景视频用 8.3 短路径播放: {buf.value}")
                    return str(buf.value)
        except Exception:
            pass
        # ② 复制到纯 ASCII 目录（放 D 盘，避免占 C 盘）
        try:
            import shutil
            ext = os.path.splitext(src)[1] or ".mp4"
            for base in ("D:" + os.sep + "AIpetBgCache",
                         os.path.join(os.environ.get("TEMP", ""), "AIpetBg")):
                if not base or not base.isascii():
                    continue
                os.makedirs(base, exist_ok=True)
                dst = os.path.join(base, "bg_loop" + ext)
                if (not os.path.isfile(dst)) or os.path.getsize(dst) != os.path.getsize(src):
                    shutil.copy2(src, dst)
                print(f"[NewUI] 背景视频路径含中文 → 已复制到 {dst} 播放")
                return dst
        except Exception as e:
            print(f"[NewUI] ⚠ 复制背景视频失败（可能仍无法播放）: {e}")
    except Exception as e:
        print(f"[NewUI] ⚠ 处理视频路径失败: {e}")
    return src


def _find_python(base: str) -> str:
    for rel in (os.path.join("runtime", "venv", "Scripts", "python.exe"), "python.exe"):
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    return sys.executable if not getattr(sys, "frozen", False) else ""


def _local_opener():
    """访问本机服务用的 opener：显式禁用代理。

     挂加速器/梯子时系统代理（注册表）会把 127.0.0.1 也送去代理 →
       启动器一直显示"桌宠：未运行"、也无法"关闭桌宠"（用户反馈）。
       这里直接不带代理发请求，最可靠。
    """
    try:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    except Exception:
        return urllib.request.build_opener()


def _local_open(req, timeout=3):
    return _local_opener().open(req, timeout=timeout)


def _pet_pid_alive() -> bool:
    """桌宠进程还活着吗（读 data/pet.pid）——**启动期间**端口还没起，只能靠它判断。

    用户反馈："启动时按钮有时候会变回启动桌宠，点了就开第二只" ——
    根因就是这里以前只探测 HTTP 端口，而桌宠启动要三十秒，
    期间端口探测失败 → 按钮变回「启动桌宠」→ 再点就拉起第二个。
    """
    try:
        import ctypes
        pf = os.path.join(_app_base_dir(), "data", "pet.pid")
        if not os.path.exists(pf):
            return False
        with open(pf, encoding="utf-8") as f:
            pid = int((f.read() or "0").strip() or 0)
        if pid <= 0:
            return False
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        k32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong(0)
            ok = k32.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code))
            return bool(ok) and code.value == 259
        finally:
            try:
                k32.CloseHandle(ctypes.c_void_p(h))
            except Exception:
                pass
    except Exception:
        return False


def _pet_api_alive() -> bool:
    try:
        req = urllib.request.Request(_CONTROL_BASE, method="GET")
        with _local_open(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _send_control(feature: str):
    try:
        req = urllib.request.Request(f"{_CONTROL_BASE}/{feature}", method="POST", data=b"")
        with _local_open(req, timeout=5) as r:
            r.read()
    except Exception as e:
        print(f"[NewUI] 控制指令 {feature} 失败: {e}")


# ══════════════════════ 小部件 ══════════════════════
class NavRailButton(QPushButton):
    """左栏导航按钮：主题有目录图标就用图标，没有就用 emoji

    （千恋万花等主题在 theme.json 的 nav_icons 里声明图标路径，
      例如 assets/nav/model.png；新外壳直接读取它。）"""

    def __init__(self, icon, title, subtitle="", parent=None, icon_key=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(58)   # 图标放大后按钮同步加高
        self._title, self._subtitle, self._icon = title, subtitle, icon
        self._icon_key = icon_key
        self._accent = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")
        self._pix = None
        self.reload_theme_icon()
        self._apply_style()

    def reload_theme_icon(self):
        """按当前主题重取导航图标（换主题后不用重启 → 图标跟着换）"""
        self._pix = None
        try:
            self.setIcon(QIcon())
        except Exception:
            pass
        if not self._icon_key:
            return
        try:
            from .colors import nav_icon_path
            art = nav_icon_path(self._icon_key)
            if art:
                pm = QPixmap(art)
                if not pm.isNull():
                    h = 33            # 目录图标放大 1.5 倍（原 22）
                    w = max(1, int(pm.width() * h / max(1, pm.height())))
                    self._pix = pm.scaled(min(w, 40), h, Qt.KeepAspectRatio,
                                          Qt.SmoothTransformation)
                    self.setIcon(QIcon(self._pix))
                    self.setIconSize(self._pix.size())
        except Exception as e:
            print(f"[NewUI]  主题导航图标加载失败({self._icon_key}): {e}")

    def _apply_style(self):
        """样式只设一次：选中/悬停交给 QSS 伪状态，避免每次点击都重新解析样式表（卡顿源）"""
        if self._pix is not None:
            self.setText(f"   {self._title}")       # 用主题图标，不再叠 emoji
        else:
            self.setText(f" {self._icon}   {self._title}")
        self.setToolTip(self._subtitle or self._title)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Color1.name()}; border: none; text-align: left;
                padding: 4px 10px; border-radius: 10px; font-family: "{silicon_ui.M.font}";
                font-size: 14px; font-weight: 500;
            }}
            QPushButton:hover {{ background: {SF(0.12)}; }}
            QPushButton:checked {{ background: {self._accent}; color: white; font-weight: bold; }}
        """)

    def _refresh(self):
        self._apply_style()

    def set_accent(self, hexcolor: str):
        self._accent = hexcolor
        self._apply_style()


class StatusChip(QLabel):
    """状态小胶囊：圆点 + 文本（绿=在线/灰=离线）"""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.set_text(text, False)

    def set_text(self, text, ok: bool):
        if getattr(self, "_last", None) == (text, ok):
            return
        self._last = (text, ok)
        dot = "#5fd3a0" if ok else "#6d7688"
        self.setText(f"<span style='color:{dot};'>●</span> {text}")
        self.setStyleSheet(
            f"QLabel {{ background: {SF(0.09)}; border: 1px solid {Color5.name()};"
            f" border-radius: 12px; padding: 4px 12px; color: {Gray2.name()};"
            f" font-family: '{silicon_ui.M.font}'; font-size: 12px; }}")


def Card(parent=None) -> QFrame:
    """卡片容器（半透明面 + 细描边 + 圆角）"""
    f = QFrame(parent)
    f.setStyleSheet(
        f"QFrame {{ background: {SF(0.07)}; border: 1px solid {Color5.name()};"
        f" border-radius: {silicon_ui.M.radius_card}px; }}")
    return f


def _accent_btn_qss(accent: str, danger: bool = False) -> str:
    c1 = "#e03030" if danger else accent
    c2 = "#f06060" if danger else QColor(accent).lighter(125).name()
    return f"""
QPushButton {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c1}, stop:1 {c2});
    color: white; border: 1px solid rgba(255,255,255,0.25); border-radius: 10px;
    padding: 10px 20px; font-size: 14px; font-weight: bold;
    font-family: "{silicon_ui.M.font}";
}}
QPushButton:hover {{ background: {c2}; }}
QPushButton:pressed {{ background: {c1}; }}
QPushButton:disabled {{ background: rgba(255,255,255,0.10); color: rgba(255,255,255,0.45);
    border-color: rgba(255,255,255,0.10); }}
"""


def _ghost_btn_qss() -> str:
    return f"""
QPushButton {{
    background: {SF(0.08)}; color: {Color1.name()};
    border: 1px solid {Color5.name()}; border-radius: 9px; padding: 9px 16px;
    font-size: 13px; font-family: "{silicon_ui.M.font}";
}}
QPushButton:hover {{ background: {SF(0.16)}; border-color: {Color3.name()}; }}
"""


# ══════════════════════ 总览页 ══════════════════════
class HomePage(QWidget):
    """总览：启动/关闭桌宠、QQ、微信 + 控制面板 + 运行状态"""

    _probe_signal = pyqtSignal()
    _models_probe_signal = pyqtSignal()   # 模型余额查询结果回到界面线程

    def __init__(self, shell, parent=None):
        super().__init__(parent)
        self.shell = shell
        # 子进程句柄挂在 shell 上（换肤会重建本页 → 重建后仍能看到「QQ：运行中」）

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 16, 22, 18)
        outer.setSpacing(14)

        accent = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")

        # ── 顶部：标题 + 状态胶囊 ──
        head = QHBoxLayout()
        title = QLabel("总览")
        title.setStyleSheet(f"color: {Color1.name()}; font-size: 22px; font-weight: bold;"
                            f" font-family: '{silicon_ui.M.font}';")
        head.addWidget(title)
        head.addStretch()
        self.chip_pet = StatusChip("桌宠：未运行")
        self.chip_qq = StatusChip("QQ：未运行")
        self.chip_tts = StatusChip("语音服务：未知")
        self.chip_vision = StatusChip("视觉服务：未知")
        for c in (self.chip_pet, self.chip_qq, self.chip_tts, self.chip_vision):
            head.addWidget(c)
        outer.addLayout(head)

        # ── 启动卡片 ──
        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)
        row = QHBoxLayout()
        self.btn_pet = QPushButton("  启动 AIpet 桌宠")
        self.btn_pet.setStyleSheet(_accent_btn_qss(accent))
        self.btn_pet.setMinimumHeight(46)
        self.btn_pet.clicked.connect(self.toggle_pet)
        self.btn_qq = QPushButton("  启动 QQ AIpet")
        self.btn_qq.setStyleSheet(_ghost_btn_qss())
        self.btn_qq.setMinimumHeight(46)
        self.btn_qq.clicked.connect(self.start_qq)
        self.btn_wx = QPushButton("  启动微信 AIpet")
        self.btn_wx.setStyleSheet(_ghost_btn_qss())
        self.btn_wx.setMinimumHeight(46)
        self.btn_wx.clicked.connect(self.start_wechat)
        # 预载语音服务：提前把 TTS 启动+预热好，之后再启动桌宠，第一句话不用等冷启动
        self.btn_preload = QPushButton("  预载语音服务")
        self.btn_preload.setStyleSheet(_ghost_btn_qss())
        self.btn_preload.setMinimumHeight(46)
        self.btn_preload.setToolTip(
            "提前启动并预热语音服务（GPT-SoVITS）：\n"
            "首次加载模型要 1~2 分钟，预热后桌宠开口几乎不用等。\n"
            "预载完成后按钮显示「预载完成」。")
        self.btn_preload.clicked.connect(self.preload_tts)
        # 预载视觉服务：本地视觉模型加载 + 预热约 30 秒，先点这个再启动桌宠，识别不用等冷启动
        self.btn_vpreload = QPushButton("  预载视觉服务")
        self.btn_vpreload.setStyleSheet(_ghost_btn_qss())
        self.btn_vpreload.setMinimumHeight(46)
        self.btn_vpreload.setToolTip(
            "提前启动本地视觉服务（屏幕/摄像头识别用的那个模型）：\n"
            "加载 + 预热约 30 秒，预载后桌宠第一屏识别就不用等。\n"
            "不预载也没关系：启动桌宠时会自动拉起。")
        self.btn_vpreload.clicked.connect(self.preload_vision)
        for b in (self.btn_pet, self.btn_qq, self.btn_wx, self.btn_preload, self.btn_vpreload):
            row.addWidget(b)
        row.addStretch()
        cl.addLayout(row)

        tip = QLabel("启动桌宠后可用下方按钮实时控制；QQ 首次使用需扫码登录（需要手机 QQ）。")
        tip.setStyleSheet(f"color: {Gray2.name()}; font-size: 12px;")
        cl.addWidget(tip)
        outer.addWidget(card)

        # ── 模型状态卡片：语言模型 / 视觉模型 各一行（模型名 + 来源 + 余额）──
        models = Card()
        ml = QVBoxLayout(models)
        ml.setContentsMargins(18, 14, 18, 16)
        ml.setSpacing(8)
        ml.addWidget(silicon_ui.section_title("模型状态", accent))
        self.model_rows = {}
        for _k, _icon, _title, _hint in (
                ("lang", "", "语言模型", "对话用的模型"),
                ("vision", "", "视觉模型", "屏幕/摄像头识别用的模型")):
            row = QHBoxLayout()
            row.setSpacing(8)
            tag = QLabel(f"{(_icon + ' ') if _icon else ''}{_title}")
            tag.setStyleSheet(f"color: {Gray2.name()}; font-size: 12px;"
                              f" font-family: '{silicon_ui.M.font}';")
            tag.setFixedWidth(int(78 * S))
            tag.setToolTip(_hint)
            name_lbl = QLabel("检测中…")
            name_lbl.setStyleSheet(f"color: {Color1.name()}; font-size: 13px;"
                                   f" font-family: '{silicon_ui.M.font}';")
            bal_lbl = QLabel("")
            bal_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: 13px;"
                                  f" font-family: '{silicon_ui.M.font}';")
            bal_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(tag)
            row.addWidget(name_lbl, 1)
            row.addWidget(bal_lbl)
            ml.addLayout(row)
            self.model_rows[_k] = (name_lbl, bal_lbl)
        # 卡片位置放到最后（快捷工具下面）——见文件末尾的 addWidget
        # 余额要联网查，不能跟着 6 秒的状态刷新跑 → 单独的定时器（60 秒一次，后台线程里查）
        self._models_probe_signal.connect(self._apply_models)
        try:
            from PyQt5.QtCore import QTimer as _QT
            self._models_timer = _QT(self)
            self._models_timer.setInterval(60000)
            self._models_timer.timeout.connect(self.refresh_models)
            self._models_timer.start()
            _QT.singleShot(1200, self.refresh_models)
        except Exception:
            pass

        # ── 剧情模式（Galgame）入口：只放一个按钮 ──
        # 正式版没有剧情模块（story/ 被移除）→ 直接不显示这个入口，免得点了报错
        _has_story = os.path.isdir(os.path.join(_app_base_dir(), "story"))
        for _f in ("剧情素材", "story"):
            if not os.path.exists(os.path.join(_app_base_dir(), _f)):
                _has_story = False
                break
        if not _has_story:
            print("[NewUI] 未包含剧情模块 → 隐藏「剧情模式」入口（正式版）")
        st_row = QHBoxLayout()
        b_story = QPushButton("  剧情模式")
        b_story.setStyleSheet(_accent_btn_qss(accent))
        b_story.setMinimumHeight(52)
        f = b_story.font()
        f.setPointSize(max(11, f.pointSize() + 2))
        f.setBold(True)
        b_story.setFont(f)
        b_story.setToolTip("进入 Galgame 风格的剧情玩法（独立窗口）")
        b_story.clicked.connect(self._open_story)
        st_row.addWidget(b_story, 1)
        if _has_story:
            outer.addLayout(st_row)

        # ── 控制面板卡片 ──
        ctl = Card()
        cl2 = QVBoxLayout(ctl)
        cl2.setContentsMargins(18, 14, 18, 16)
        cl2.setSpacing(10)
        cl2.addWidget(silicon_ui.section_title("桌宠控制面板", accent))
        grid = QHBoxLayout()
        for text, feat in ((" 汉语模式", "longtext"), (" Live2D", "live2d"),
                           (" 摄像头识别", "camera"), (" 屏幕识别", "screenshot"),
                           (" 按住说话", "voice")):
            b = QPushButton(text)
            b.setStyleSheet(_ghost_btn_qss())
            b.setMinimumHeight(38)
            if feat == "voice":
                b.pressed.connect(lambda: _send_control("voice/start"))
                b.released.connect(lambda: _send_control("voice/end"))
            else:
                b.clicked.connect(lambda _=False, f=feat: _send_control(f))
            grid.addWidget(b)
        # 重置桌宠位置：桌宠跑到屏幕外 / 找不到时一键回到屏幕中央
        self.btn_reset_pos = QPushButton(" 重置桌宠位置")
        self.btn_reset_pos.setStyleSheet(_ghost_btn_qss())
        self.btn_reset_pos.setMinimumHeight(38)
        self.btn_reset_pos.setToolTip("把桌宠移回屏幕中央（找不到桌宠时点这里）")
        self.btn_reset_pos.clicked.connect(self.reset_pet_pos)
        grid.addWidget(self.btn_reset_pos)
        grid.addStretch()
        cl2.addLayout(grid)
        # 控制面板下面的一行状态提示
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: 12px;")
        cl2.addWidget(self.status_lbl)
        outer.addWidget(ctl)

        # ── 快捷工具卡片 ──
        tools = Card()
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(18, 14, 18, 16)
        tl.setSpacing(10)
        tl.addWidget(silicon_ui.section_title("快捷工具", accent))
        tr = QHBoxLayout()
        for text, slot in ((" 立绘工坊", self.open_studio),
                           (" 桌宠设置", self.open_pet_settings),
                           (" NapCat WebUI", self.open_napcat_webui),
                           (" 重新扫码登录", self.napcat_relogin),
                           (" 打开程序目录", self.open_app_dir),
                           (" 更新日志", self.open_changelog)):
            b = QPushButton(text)
            b.setStyleSheet(_ghost_btn_qss())
            b.clicked.connect(slot)
            tr.addWidget(b)
        tr.addStretch()
        tl.addLayout(tr)
        outer.addWidget(tools)
        # ── 模型状态卡片放最底下（语言模型 / 视觉模型：模型名 + 余额）──
        outer.addWidget(models)
        outer.addStretch()

        self._probe_signal.connect(self._apply_status)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(6000)

    # ── 状态 ──
    def refresh_models(self):
        """后台线程查两个模型的余额（联网查询绝不能放界面线程）"""
        if getattr(self, "_models_busy", False):
            return
        self._models_busy = True

        def _work():
            res = {}
            try:
                info = _models_info()
                for k in ("lang", "vision"):
                    it = info.get(k) or {}
                    res[k] = (it.get("model") or "未配置",
                              _balance_for(str(it.get("provider") or ""), str(it.get("key") or "")))
            except Exception as e:
                print(f"[NewUI]  模型状态查询失败: {e}")
                res = {"lang": ("查询失败", "—"), "vision": ("查询失败", "—")}
            self._models_result = res
            try:
                self._models_probe_signal.emit()
            except Exception:
                pass

        import threading
        threading.Thread(target=_work, daemon=True).start()

    def _apply_models(self):
        self._models_busy = False
        res = getattr(self, "_models_result", None) or {}
        for k, widgets in (getattr(self, "model_rows", None) or {}).items():
            name_lbl, bal_lbl = widgets
            model, bal = res.get(k, ("未配置", "—"))
            try:
                name_lbl.setText(str(model))
                bal_lbl.setText(str(bal))
                # 余额少的标红提醒（本地部署/查询失败保持灰色）
                warn = False
                s = str(bal)
                if s.startswith(("¥", "$")):
                    try:
                        warn = float(s[1:]) < 5.0
                    except Exception:
                        warn = False
                bal_lbl.setStyleSheet(
                    f"color: {'#e0603a' if warn else '#3d9e6a' if s and not warn and '无费用' in s else Gray2.name()};"
                    f" font-size: 13px; font-family: '{silicon_ui.M.font}';")
            except Exception as e:
                print(f"[NewUI]  模型状态显示失败: {e}")

    def refresh_status(self):
        """后台线程探测运行状态（绝不在 UI 线程做网络探测 → 不卡界面）"""
        if getattr(self, "_probe_busy", False):
            return
        self._probe_busy = True

        def _work():
            # 端口或进程锁任一活着 → 算"运行中"（启动期间只有进程锁在）
            alive = _pet_api_alive()
            if not alive:
                try:
                    alive = _pet_pid_alive()
                except Exception:
                    pass
            tts_ok = False
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.4)
                    tts_ok = s.connect_ex(("127.0.0.1", 9880)) == 0
            except Exception:
                pass
            # 视觉：设置成云端就显示「云端」，本地就探服务端口在不在
            vis_state = "unknown"
            try:
                _cfg = _vision_cfg()
                if str(_cfg.get("vision_source") or "local").strip().lower() != "local":
                    vis_state = "cloud"
                else:
                    vis_state = "online" if _vision_alive(_vision_port(_cfg)) else "offline"
            except Exception:
                pass
            self._probe_result = (alive, tts_ok, vis_state)
            try:
                self._probe_signal.emit()
            except Exception:
                pass

        import threading
        threading.Thread(target=_work, daemon=True).start()

    def _apply_status(self):
        """探测结果回到 UI 线程再更新（信号触发）"""
        try:
            alive, tts_ok, vis_state = getattr(self, "_probe_result", (False, False, "unknown"))
            self._probe_busy = False
            self.chip_pet.set_text("桌宠：运行中" if alive else "桌宠：未运行", alive)
            # 「正在关闭/启动中」期间不要被状态刷新覆盖文案
            if self.btn_pet.isEnabled():
                self.btn_pet.setText("   关闭桌宠" if alive else "  启动 AIpet 桌宠")
            accent = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")
            self.btn_pet.setStyleSheet(_accent_btn_qss(accent, danger=alive))
            try:
                self.btn_reset_pos.setEnabled(alive)
                if self.btn_reset_pos.isEnabled():
                    self.btn_reset_pos.setText(" 重置桌宠位置")
            except Exception:
                pass
            qq_on = self.shell._qq_proc is not None and self.shell._qq_proc.poll() is None
            self.chip_qq.set_text("QQ：运行中" if qq_on else "QQ：未运行", qq_on)
            self.chip_tts.set_text("语音服务：在线" if tts_ok else "语音服务：未启动", tts_ok)
            try:
                if vis_state == "cloud":
                    self.chip_vision.set_text("视觉识别：云端", True)
                elif vis_state == "online":
                    self.chip_vision.set_text("视觉服务：在线", True)
                elif vis_state == "offline":
                    self.chip_vision.set_text("视觉服务：离线", False)
                else:
                    self.chip_vision.set_text("视觉服务：未知", False)
            except Exception:
                pass
        except Exception as e:
            print(f"[NewUI]  状态更新失败: {e}")

    # ── 启动/关闭 ──
    # ── 启动/关闭：进行中按钮置灰 + 文案，防止连点 ──
    def _busy_btn(self, btn, text: str, ms: int = 6000):
        try:
            btn.setEnabled(False)
            btn.setText("  " + text)
            QTimer.singleShot(ms, lambda: (btn.setEnabled(True), self.refresh_status()))
        except Exception:
            pass

    def _open_story(self, hash_q: str = ""):
        """打开剧情模式：起本地服务 + 浏览器内核的独立窗口（像 galgame 本体）"""
        try:
            from story import launch as story_launch
            url = ""
            if hash_q:
                try:
                    s = story_launch.srv.ensure_server()
                    url = s.url + hash_q
                except Exception:
                    url = ""
            story_launch.open_story_window(url)
            if not getattr(self, "_story_timer", None):
                self._story_timer = QTimer(self)
                self._story_timer.setInterval(1000)
                self._story_timer.timeout.connect(story_launch.tick)
                self._story_timer.start()
            return None
        except Exception as e:
            print(f"[UI]  打开剧情窗口失败: {e}")
            return None

    def _story_continue(self):
        try:
            from story import store as story_store
            ss = story_store.list_stories()
            self._open_story(("#play=" + str(ss[0]["id"])) if ss else "")
        except Exception:
            self._open_story()

    def _story_flow(self):
        try:
            import urllib.parse

            from story import store as story_store
            ss = story_store.list_stories()
            if ss:
                self._open_story("#screen=flow&sid=" + urllib.parse.quote(str(ss[0]["id"])))
            else:
                self._open_story()
        except Exception:
            self._open_story()

    def toggle_pet(self):
        _running = _pet_api_alive()
        if not _running:
            try:
                _running = _pet_pid_alive()
            except Exception:
                pass
        if _running and not _pet_api_alive():
            # 进程在、端口还没起 = 正在启动：别当作"未运行"去再拉一只
            self._busy_btn(self.btn_pet, " 正在启动中…", 30000)
            self.status_lbl.setText(" 桌宠正在启动，请稍候…")
            QTimer.singleShot(6000, self.refresh_status)
            print("[NewUI] 桌宠正在启动中（进程已在）→ 不再启动第二只")
            return
        if _running:
            # 关闭桌宠：显示「正在关闭中…」并禁用按钮，避免重复点击
            self._busy_btn(self.btn_pet, " 正在关闭中…", 8000)
            self.status_lbl.setText(" 正在关闭桌宠…")
            QTimer.singleShot(9000, lambda: self.status_lbl.setText(""))
            print("[NewUI] 正在关闭桌宠…")
            _send_control("shutdown")
            # 桌宠不用了：把本地视觉服务也收掉，显卡（6G 显存）让给别的程序
            try:
                stop_vision_service(self.shell)
            except Exception as e:
                print(f"[NewUI]  关闭本地视觉服务失败: {e}")
            # 轮询等它真的退出（最多 12 秒），再刷新状态
            self._wait_pet_gone(12)
            return
        self._busy_btn(self.btn_pet, " 正在启动中…", 40000)
        base = _app_base_dir()
        py = _find_python(base)
        if not py:
            QMessageBox.warning(self, "启动失败", "未找到 Python 解释器（runtime/venv）")
            return
        # 本地视觉模型（屏幕/摄像头识别）跟着桌宠一起起：加载要几秒，先开好再启动桌宠
        try:
            ensure_vision_service(self.shell)
        except Exception as e:
            print(f"[NewUI]  启动本地视觉服务失败（不影响桌宠）: {e}")
        try:
            self.shell._pet_proc = subprocess.Popen([py, os.path.join(base, "run.py")], cwd=base,
                                                    creationflags=_spawn_flags())
            print("[NewUI] 已启动桌宠（run.py）")
            QTimer.singleShot(6000, self.refresh_status)
        except Exception as e:
            QMessageBox.warning(self, "启动失败", str(e))

    def _wait_pet_gone(self, seconds: int):
        """后台轮询：桌宠真的退出了再恢复按钮（期间保持「正在关闭中…」）"""
        def _work():
            import time as _t
            for _ in range(int(seconds * 2)):
                _t.sleep(0.5)
                if not _pet_api_alive():
                    break
            try:
                self._probe_signal.emit()
            except Exception:
                pass
        import threading
        threading.Thread(target=_work, daemon=True).start()

    def reset_pet_pos(self):
        """把桌宠移回屏幕中央（找不到桌宠时用）"""
        if not _pet_api_alive():
            QMessageBox.information(self, "重置桌宠位置", "桌宠还没启动哦，先点「启动 AIpet 桌宠」。")
            return
        self._busy_btn(self.btn_reset_pos, " 正在移动…", 4000)
        _send_control("reset_position")
        self.status_lbl.setText(" 让桌宠回到屏幕中央…")
        QTimer.singleShot(4500, lambda: self.status_lbl.setText(""))
        print("[NewUI] 已发送「重置桌宠位置」")

    def start_qq(self):
        base = _app_base_dir()
        py = _find_python(base)
        if not py:
            return
        self._busy_btn(self.btn_qq, " 正在启动 QQ…", 12000)
        try:
            self.shell._qq_proc = subprocess.Popen([py, os.path.join(base, "run_qq.py")], cwd=base,
                                                   creationflags=_spawn_flags())
            self.refresh_status()
        except Exception as e:
            QMessageBox.warning(self, "启动失败", str(e))

    def start_wechat(self):
        base = _app_base_dir()
        py = _find_python(base)
        if not py or not os.path.exists(os.path.join(base, "run_wechat.py")):
            QMessageBox.information(self, "微信 AIpet", "未找到微信模块（run_wechat.py）")
            return
        self._busy_btn(self.btn_wx, " 正在启动微信…", 12000)
        try:
            self.shell._wx_proc = subprocess.Popen([py, os.path.join(base, "run_wechat.py")], cwd=base,
                                                   creationflags=_spawn_flags())
        except Exception as e:
            QMessageBox.warning(self, "启动失败", str(e))

    def preload_tts(self):
        """预载语音服务：启动 + 预热，过程直接显示在按钮上。

        线程只负责读子进程输出（纯数据），界面更新一律走主线程的 QTimer 轮询 ——
        Qt 不允许在别的线程里动控件（跨线程 QTimer.singleShot 不会生效，按钮会一直卡在"预载中"）。
        """
        import threading
        base = _app_base_dir()
        py = _find_python(base)
        script = os.path.join(base, "tool", "tts_service.py")
        if not py or not os.path.exists(script):
            QMessageBox.information(self, "预载语音服务", "未找到语音服务脚本（tool/tts_service.py）")
            return
        self.btn_preload.setEnabled(False)
        self.btn_preload.setText("  预载中…")
        self._preload_steps = []
        try:
            # 输出自己读（按钮上显示进度）→ 一律不弹控制台窗口
            self.shell._tts_proc = subprocess.Popen(
                [py, script, "preload"], cwd=base,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        except Exception as e:
            self._preload_done(False, str(e))
            return

        def _reader():
            try:
                for line in iter(self.shell._tts_proc.stdout.readline, ""):
                    line = (line or "").strip()
                    if line:
                        self._preload_steps.append(line)      # 只放数据，不碰界面
            except Exception:
                pass

        threading.Thread(target=_reader, daemon=True).start()

        # 主线程轮询：更新按钮文字 / 结束时收尾
        self._preload_timer = QTimer(self)
        self._preload_timer.setInterval(500)

        def _tick():
            proc = getattr(self.shell, "_tts_proc", None)
            if self._preload_steps:
                msg = self._preload_steps[-1].replace("[预载]", "").strip()
                if not self.btn_preload.text().endswith(msg[:14] + "…"):
                    self.btn_preload.setText(f"  {msg[:14]}…")
            if proc is None or proc.poll() is not None:
                self._preload_timer.stop()
                self._preload_done(proc is not None and proc.returncode == 0, "")

        self._preload_timer.timeout.connect(_tick)
        self._preload_timer.start()

    def _preload_done(self, ok, err=""):
        self.btn_preload.setEnabled(True)
        if ok:
            self.btn_preload.setText("  预载完成")
            QTimer.singleShot(10000, lambda: self.btn_preload.setText("  预载语音服务"))
        else:
            self.btn_preload.setText("  预载失败（可重试）")
            QTimer.singleShot(10000, lambda: self.btn_preload.setText("  预载语音服务"))
            if err:
                print(f"[NewUI]  语音预载失败: {err}")
        try:
            self.refresh_status()
        except Exception:
            pass

    # ── 本地视觉服务预载 ──
    def _vision_health(self, port: int) -> dict:
        """问一下本地视觉服务：起来了没 / 模型加载完了没（出错返回空字典）"""
        try:
            import json as _json
            import urllib.request as _ur
            op = _ur.build_opener(_ur.ProxyHandler({}))          # 本机请求别走代理
            with op.open(f"http://127.0.0.1:{int(port)}/", timeout=1.5) as r:
                return _json.loads(r.read().decode("utf-8", "ignore")) or {}
        except Exception:
            return {}

    def preload_vision(self):
        """预载本地视觉服务：把服务起起来并等模型加载好（约 30 秒，进度显示在按钮上）。

        预载只是"提前热身"：不点也会在启动桌宠时自动拉起。
        """
        import time as _t
        cfg = _vision_cfg()
        if str(cfg.get("vision_source") or "local").strip().lower() != "local":
            QMessageBox.information(
                self, "预载视觉服务",
                "当前「识别来源」是云端 API，不需要本地视觉服务。\n\n"
                "想用本地模型：设置 → 视觉模型 → 识别来源改成「本地视觉模型」。")
            return
        base = _app_base_dir()
        if not os.path.isfile(os.path.join(base, "tool", "vision_service.py")):
            QMessageBox.information(self, "预载视觉服务",
                                    "未找到 tool/vision_service.py（安装包可能不完整）")
            return
        port = _vision_port(cfg)
        self.btn_vpreload.setEnabled(False)
        self.btn_vpreload.setText("  预载中…")
        self._vpre_t0 = _t.time()
        self._vpre_ready = False
        if not _vision_alive(port):
            try:
                ensure_vision_service(self.shell)
            except Exception as e:
                print(f"[NewUI]  预载视觉服务失败: {e}")
        # 主线程轮询状态（探测都是本机几毫秒的请求，不会卡界面）
        self._vpre_timer = QTimer(self)
        self._vpre_timer.setInterval(2000)

        def _tick():
            if not _vision_alive(port):
                if _t.time() - self._vpre_t0 > 180:
                    self._vpre_timer.stop()
                    self._vpre_done(False)
                return
            h = self._vision_health(port)
            if h.get("ok"):
                self._vpre_ready = True
                self._vpre_timer.stop()
                self._vpre_done(True)
            elif h.get("error"):
                self._vpre_timer.stop()
                self._vpre_done(False, str(h.get("error"))[:60])
            else:
                el = int(_t.time() - self._vpre_t0)
                self.btn_vpreload.setText(f"  模型加载中… {el}s")

        self._vpre_timer.timeout.connect(_tick)
        self._vpre_timer.start()
        _tick()

    def _vpre_done(self, ok, err=""):
        self.btn_vpreload.setEnabled(True)
        if ok:
            self.btn_vpreload.setText("  预载完成")
            QTimer.singleShot(10000, lambda: self.btn_vpreload.setText("  预载视觉服务"))
        else:
            self.btn_vpreload.setText("  预载失败（可重试）")
            QTimer.singleShot(12000, lambda: self.btn_vpreload.setText("  预载视觉服务"))
            if err:
                print(f"[NewUI]  视觉预载失败: {err}")
        try:
            self.refresh_status()
        except Exception:
            pass

    # ── 工具 ──
    def open_studio(self):
        try:
            from .portrait_studio import PortraitStudio
            # 挂在外壳上：换肤重建总览页后仍是同一个工坊实例
            self._studio = getattr(self.shell, "_portrait_studio", None) or PortraitStudio(self.window())
            self.shell._portrait_studio = self._studio
            self._studio.show(); self._studio.raise_(); self._studio.activateWindow()
        except Exception as e:
            QMessageBox.warning(self, "立绘工坊", f"打开失败：{e}")

    def open_pet_settings(self):
        try:
            from .pet_wizard import PCLPetWizard
            from pets.pet_registry import get_active_pet_id
            dlg = PCLPetWizard(get_active_pet_id(), self.window())
            dlg.show(); dlg.raise_(); dlg.activateWindow()   # 非模态，避免锁住预览窗口
        except Exception as e:
            QMessageBox.warning(self, "桌宠设置", f"打开失败：{e}")

    def open_napcat_webui(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:6099")
        print("[NewUI] 已打开 NapCat WebUI（默认 6099，Token 见 config.json）")

    def napcat_relogin(self):
        base = _app_base_dir()
        bat = os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat", "launcher-user.bat")
        if os.path.exists(bat):
            try:
                subprocess.Popen([bat], cwd=os.path.dirname(bat),
                                 creationflags=_spawn_flags())
                QMessageBox.information(self, "重新扫码登录",
                                        "已打开 NapCat 登录窗口，请用手机 QQ 扫描二维码。\n"
                                        "二维码也已保存到：NapCat.Shell.Windows.OneKey\\NapCat\\cache\\qrcode.png")
            except Exception as e:
                QMessageBox.warning(self, "重新登录", str(e))
        else:
            QMessageBox.information(self, "重新登录", "未找到 NapCat 启动脚本")

    def open_app_dir(self):
        try:
            os.startfile(_app_base_dir())    # noqa
        except Exception as e:
            print(f"[NewUI] 打开目录失败: {e}")

    def open_changelog(self):
        import glob
        base = _app_base_dir()
        files = sorted(glob.glob(os.path.join(base, "更新日志", "*")), reverse=True)
        if not files:
            QMessageBox.information(self, "更新日志", "未找到更新日志文件")
            return
        try:
            os.startfile(files[0])           # noqa
        except Exception as e:
            QMessageBox.information(self, "更新日志", f"打开失败：{e}")


# ══════════════════════ 主窗口 ══════════════════════
class SiliconLauncher(QWidget):
    """AIpet 启动器 · 新版外壳"""

    def __init__(self):
        super().__init__()
        _ensure_src_on_path()        # 冻结版：页面懒加载用得到随包源码
        self._pet_proc = None
        self._qq_proc = None
        self._wx_proc = None
        self._vision_proc = None     # 本地视觉服务（起桌宠时拉起，桌宠关了收掉）
        self._bg_widget = None
        self._media = None
        self._video_bg = None

        self.setWindowTitle("AIpet 丛雨桌宠 · 启动器")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(1200, 780)
        self.setMinimumSize(1000, 680)

        from .colors import current_theme_id
        self._silicon = current_theme_id() == "silicon"
        self._accent = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        self._base_color = QColor(Color8)
        self.back = _RoundBack(self._base_color, self)
        root.addWidget(self.back)
        inner = QVBoxLayout(self.back)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        inner.addWidget(self._build_titlebar())

        body = QHBoxLayout()
        body.setContentsMargins(10, 8, 10, 10)
        body.setSpacing(10)
        body.addWidget(self._build_nav())
        body.addWidget(self._build_stack(), 1)
        inner.addLayout(body, 1)

        if self._silicon:
            QTimer.singleShot(60, self._apply_effects)
        self._load_background()

    # ── 标题栏 ──
    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 6, 10, 6)
        lay.setSpacing(10)

        ico = QLabel()
        p = os.path.join(_app_base_dir(), "icon.png")
        if os.path.exists(p):
            pm = QPixmap(p)
            if not pm.isNull():
                ico.setPixmap(pm.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(ico)
        t = QLabel("AIpet 丛雨桌宠 · 启动器")
        t.setStyleSheet(f"color: {Color1.name()}; font-size: 15px; font-weight: bold;"
                        f" font-family: '{silicon_ui.M.font}';")
        lay.addWidget(t)
        self._title = t
        lay.addStretch()

        self._chrome_btns = []          # 最小化/关闭（换肤时一起重上样式）
        for text, slot, tip in (("—", self.showMinimized, "最小化"),
                                ("×", self.close, "关闭")):
            b = QPushButton(text)
            b.setFixedSize(36, 30)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            self._chrome_btns.append((b, text))
            self._style_chrome_btn(b, text)
            lay.addWidget(b)
        # 拖动窗口
        def _press(e):
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
        def _move(e):
            if getattr(self, "_drag", None) and e.buttons() & Qt.LeftButton:
                self.move(e.globalPos() - self._drag)
        def _release(e):
            self._drag = None
        bar.mousePressEvent = _press
        bar.mouseMoveEvent = _move
        bar.mouseReleaseEvent = _release
        self._bar = bar
        return bar

    # ── 左导航栏 ──
    def _nav_rail_qss(self) -> str:
        return (f"QFrame {{ background: {SF(0.06)}; border: 1px solid {Color5.name()};"
                f" border-radius: {silicon_ui.M.radius_card}px; }}")

    def _style_chrome_btn(self, b, text: str):
        """标题栏按钮样式（抽出来是为了换肤时能重上）"""
        b.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Color1.name()};
                border: none; border-radius: 8px; font-size: 14px; }}
            QPushButton:hover {{ background: {'#e03030' if text == '×' else SF(0.16)};
                color: {'white' if text == '×' else Color1.name()}; }}
        """)

    def _build_nav(self) -> QWidget:
        rail = QFrame()
        rail.setFixedWidth(196)
        rail.setStyleSheet(self._nav_rail_qss())
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(6)

        self.nav_btns = {}
        for key, icon, title, sub in NAV:
            # 主题图标键：总览复用「模型」图标
            b = NavRailButton(icon, title, sub, icon_key=("model" if key == "home" else key))
            b.clicked.connect(lambda _=False, k=key: self._goto(k))
            b._page_key = key                       # 悬停预热用（见 eventFilter）
            b.installEventFilter(self)
            self.nav_btns[key] = b
            lay.addWidget(b)
        lay.addStretch()

        # ── 左下角：设置入口（按需求放在左下角）+ 版本信息 ──
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Color5.name()}; border: none;")
        lay.addWidget(sep)
        b_set = NavRailButton("", "设置", "模型与功能", icon_key="settings")
        b_set.clicked.connect(lambda _=False: self._goto("settings"))
        b_set._page_key = "settings"
        b_set.installEventFilter(self)
        self.nav_btns["settings"] = b_set
        lay.addWidget(b_set)
        ver = QLabel("Silicon UI · 新版")
        ver.setStyleSheet(f"color: {Gray3.name()}; font-size: 11px; padding: 2px 8px;")
        lay.addWidget(ver)
        self._nav_rail = rail
        self._nav_sep = sep
        self._nav_ver = ver
        return rail

    # ── 内容区 ──
    def _build_stack(self) -> QWidget:
        self.stack = QStackedWidget()
        self.pages = {}
        self.stack.setStyleSheet("QStackedWidget { background: transparent; }")

        # 总览页立即构建（首屏）；其余页面懒加载（进哪个才建哪个 → 启动不卡）
        self.pages = {}
        self._page_factories = {}
        self._host_page("home", lambda: HomePage(self))
        self.home = self._ensure_page("home")

        def _mk(mod, cls):
            def _f():
                try:
                    m = __import__(mod, fromlist=[cls])
                except ImportError:
                    # 冻结版兜底：该模块可能没进 exe → 用随包源码再试一次
                    _ensure_src_on_path()
                    import importlib
                    m = importlib.import_module(mod)
                return getattr(m, cls)()
            return _f

        self._host_page("pets", _mk("pcl_launcher.widgets", "PCLPetManager"))
        self._host_page("settings", _mk("pcl_launcher.widgets", "PCLSettingsPanel"))
        self._host_page("memory", _mk("pcl_launcher.widgets", "PCLMemoryManager"))
        self._host_page("prompt", _mk("pcl_launcher.widgets", "PCLPromptEditor"))
        self._host_page("plugins", _mk("pcl_launcher.plugins_panel", "PCLPluginsPanel"))
        self._host_page("themes", _mk("pcl_launcher.themes_panel", "PCLThemesPanel"))
        return self.stack

    def _host_page(self, key, factory):
        """登记页面工厂（懒加载：首次进入才真正构建，启动快很多）"""
        self._page_factories = getattr(self, "_page_factories", {})
        self._page_factories[key] = factory

    def _ensure_page(self, key):
        if key in self.pages:
            return self.pages[key]
        fac = getattr(self, "_page_factories", {}).get(key)
        if fac is None:
            return None
        try:
            w = fac()
            # 让整页（含所有子控件）不再遮挡主题背景：
            # 1) 取消自动填充；2) 把内联样式里的实心背景改成半透明（保留一点层次，文字仍清晰）
            try:
                _make_transparent(w)
            except Exception as _e:
                print(f"[NewUI]  页面透明化失败({key}): {_e}")
            #  页面会自我刷新（点「设置」→ 桌宠列表 _refresh() / 插件页 _reload()），
            #   重建出来的卡片带回内联实心背景色 → 又挡住主题壁纸（表现为「点设置后背景被遮挡」）。
            #   这里挂钩刷新方法：重建后自动再透明化一次。
            try:
                _hook_repaint_transparency(w)
            except Exception as _e:
                print(f"[NewUI]  透明化挂钩失败({key}): {_e}")
            self.pages[key] = w
            self.stack.addWidget(w)
            if key == "home":
                self.home = w
            self._wire_page_theme(w)
            return w
        except Exception as e:
            import traceback
            print(f"[NewUI]  页面 {key} 加载失败: {e}\n{traceback.format_exc()[:400]}")
            err = QLabel(f"页面加载失败：{key}\n{e}")
            err.setStyleSheet(f"color: {RedLight.name()}; padding: 20px;")
            self.pages[key] = err
            self.stack.addWidget(err)
            return err

    def _wire_page_theme(self, page):
        """页面若声明了主题信号 → 接到外壳的实时换肤上（切换主题不再重启启动器）"""
        try:
            sig = getattr(page, "theme_applied", None)
            if sig is not None and not getattr(page, "_theme_wired", False):
                sig.connect(self.apply_theme_live)
                page._theme_wired = True
            sig2 = getattr(page, "accent_changed", None)
            if sig2 is not None and not getattr(page, "_accent_wired", False):
                sig2.connect(self.apply_accent_live)
                page._accent_wired = True
        except Exception as e:
            print(f"[NewUI]  主题信号挂接失败: {e}")

    # ══════════════ 实时换肤（主题 / 强调色，无需重启）══════════════
    def _current_page_key(self):
        cur = self.stack.currentWidget()
        for k, w in self.pages.items():
            if w is cur:
                return k
        return None

    def _restyle_chrome(self):
        """外壳（标题栏 + 导航栏 + 底板渐变/壁纸）按新配色重上样式"""
        try:
            if getattr(self, "_title", None) is not None:
                self._title.setStyleSheet(
                    f"color: {Color1.name()}; font-size: 15px; font-weight: bold;"
                    f" font-family: '{silicon_ui.M.font}';")
            for b, text in getattr(self, "_chrome_btns", []):
                self._style_chrome_btn(b, text)
            rail = getattr(self, "_nav_rail", None)
            if rail is not None:
                rail.setStyleSheet(self._nav_rail_qss())
            if getattr(self, "_nav_sep", None) is not None:
                self._nav_sep.setStyleSheet(f"background: {Color5.name()}; border: none;")
            if getattr(self, "_nav_ver", None) is not None:
                self._nav_ver.setStyleSheet(
                    f"color: {Gray3.name()}; font-size: 11px; padding: 2px 8px;")
            self._accent = accent_hex()
            for b in getattr(self, "nav_btns", {}).values():
                try:
                    b.reload_theme_icon()      # 主题自带的目录图标可能变了
                    b.set_accent(self._accent)
                except Exception:
                    pass
            # 底板：底色 + 主题壁纸（主题可能自带背景图/视频）
            try:
                self._base_color = QColor(Color8)
                self.back.set_color(self._base_color)
                self.back.set_bg(QPixmap())      # 先清掉旧主题壁纸
                self.back.update()
            except Exception:
                pass
            self.reload_background()
        except Exception as e:
            print(f"[NewUI]  外壳重设样式失败: {e}")

    def _discard_other_pages(self, keep_key):
        """换肤后：除当前页外的已建页面作废（下次进入时按新配色重建 → 省时间不卡）"""
        for k, w in list(self.pages.items()):
            if k == keep_key:
                continue
            try:
                w.hide()
                self.stack.removeWidget(w)
                w.deleteLater()
            except Exception:
                pass
            self.pages.pop(k, None)

    def _drop_snap(self, snap):
        """删除页面过渡用的快照控件（幂等）。

         快照是「一张不透明的旧页面位图」叠在内容区上：只要它没被删掉，
        用户看到的就是「背景/内容被遮挡」。所以除了动画结束删除，再加一道
        硬超时兜底（动画被打断/特效对象提前释放时也能删掉）。"""
        try:
            if snap is None:
                return
            snap.hide()
            snap.setParent(None)
            snap.deleteLater()
        except Exception:
            pass

    def _fade_out_snap(self, snap, dur=210, grow=None):
        """快照淡出（动画 + 硬超时双保险）→ 保证不留遮挡层"""
        if snap is None:
            return None
        try:
            from PyQt5.QtWidgets import QGraphicsOpacityEffect
            from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
            eff = QGraphicsOpacityEffect(snap)
            eff.setOpacity(1.0)
            snap.setGraphicsEffect(eff)
            anims = []
            a1 = QPropertyAnimation(eff, b"opacity", snap)
            a1.setDuration(int(dur))
            a1.setStartValue(1.0)
            a1.setEndValue(0.0)
            a1.setEasingCurve(QEasingCurve.OutCubic)
            a1.finished.connect(lambda: self._drop_snap(snap))
            a1.start()
            anims.append(a1)
            if grow is not None:
                a2 = QPropertyAnimation(snap, b"geometry", snap)
                a2.setDuration(int(dur))
                a2.setStartValue(grow[0])
                a2.setEndValue(grow[1])
                a2.setEasingCurve(QEasingCurve.OutCubic)
                a2.start()
                anims.append(a2)
            QTimer.singleShot(int(dur) + 260, lambda: self._drop_snap(snap))   # 硬兜底
            return tuple(anims)
        except Exception as e:
            print(f"[NewUI]  快照淡出失败（直接删除）: {e}")
            self._drop_snap(snap)
            return None

    def _rebuild_page_animated(self, key):
        """重建某一页并做淡入（旧页快照淡出 → 只动一张位图，不卡）"""
        old = self.pages.pop(key, None)
        snap = None
        if old is not None:
            try:
                snap = QLabel(self.stack)
                snap.setPixmap(old.grab())
                snap.setGeometry(self.stack.rect())
                snap.setAttribute(Qt.WA_TransparentForMouseEvents)
                snap.show()
            except Exception:
                snap = None
            try:
                old.hide()
                self.stack.removeWidget(old)
                old.deleteLater()
            except Exception:
                pass
        new = self._ensure_page(key)
        if new is None:
            self._drop_snap(snap)
            return
        self.stack.setCurrentWidget(new)
        try:
            if key == "home":
                self.home = new
                if self._current_page_key() == "home":
                    self.home._timer.start(6000)
                    self.home.refresh_status()
        except Exception:
            pass
        self._fade_out_snap(snap, 220)
        for k, b in self.nav_btns.items():
            b.setChecked(k == key)

    def apply_theme_live(self, theme_id, persist=True):
        """实时应用主题：色板/全局样式/外壳/页面/背景一次到位（不重启启动器）"""
        if getattr(self, "_theming", False):
            return
        self._theming = True
        try:
            theme_id = str(theme_id or "").strip() or "silicon"
            if persist:
                try:
                    from .themes_panel import _load_config, _save_config
                    cfg = _load_config() or {}
                    cfg["ui_theme"] = theme_id
                    _save_config(cfg)
                except Exception as e:
                    print(f"[NewUI]  主题写入 config 失败: {e}")
            from . import colors as _C
            _C.apply_theme_live(theme_id)
            self._accent = _C.accent_hex()
            # 全局 QSS + 调色板（主题底色不同 → 文字深浅跟着变）
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is not None:
                    silicon_ui.install(app, accent=self._accent)
            except Exception as e:
                print(f"[NewUI]  全局样式重建失败: {e}")
            self._silicon = theme_id == "silicon"
            cur_key = self._current_page_key()
            self._restyle_chrome()
            self._discard_other_pages(cur_key)
            # 当前页重建延迟到信号返回之后（避免删除正在发信号的控件）
            if cur_key:
                QTimer.singleShot(0, lambda k=cur_key: self._rebuild_page_animated(k))
            # 已打开的二级窗口跟着换色
            try:
                from .silicon_dialog import refresh_all_dialog_colors
                refresh_all_dialog_colors()
            except Exception:
                pass
            print(f"[NewUI] 主题已实时应用: {theme_id}（当前页 {cur_key} 正在重建）")
        except Exception as e:
            print(f"[NewUI]  实时应用主题失败: {e}")
        finally:
            self._theming = False

    def apply_accent_live(self, accent_key):
        """实时应用强调色（主题色按钮）"""
        try:
            from . import colors as _C
            self._accent = _C.apply_accent_live(accent_key)
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is not None:
                    silicon_ui.install(app, accent=self._accent)
            except Exception:
                pass
            for b in getattr(self, "nav_btns", {}).values():
                try:
                    b.set_accent(self._accent)
                except Exception:
                    pass
            cur_key = self._current_page_key()
            if cur_key:
                QTimer.singleShot(0, lambda k=cur_key: self._rebuild_page_animated(k))
            try:
                from .silicon_dialog import refresh_all_dialog_colors
                refresh_all_dialog_colors()
            except Exception:
                pass
        except Exception as e:
            print(f"[NewUI]  实时应用强调色失败: {e}")

    def _goto(self, key, force=False):
        if key == "home":
            self._ensure_page("home")
        elif key not in self.pages and key not in getattr(self, "_page_factories", {}):
            return
        else:
            self._ensure_page(key)
        w = self.pages.get(key)
        if w is None:
            return
        # 过渡动画：用「旧页面快照淡出」代替整页透明度特效（后者会让重页面每帧重绘 → 卡）
        try:
            from PyQt5.QtGui import QPixmap
            from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
            from PyQt5.QtWidgets import QLabel, QGraphicsOpacityEffect
            snap = QLabel(self.stack)
            snap.setPixmap(self.stack.grab())
            snap.setGeometry(self.stack.rect())
            snap.setAttribute(Qt.WA_TransparentForMouseEvents)
            snap.setScaledContents(True)
            snap.show()
            eff = QGraphicsOpacityEffect(snap)
            eff.setOpacity(1.0)
            snap.setGraphicsEffect(eff)
            self.stack.setCurrentWidget(w)
            # 旧页淡出 + 轻微放大（只动一张位图 → 不卡）
            a1 = QPropertyAnimation(eff, b"opacity", snap)
            a1.setDuration(210)
            a1.setStartValue(1.0)
            a1.setEndValue(0.0)
            a1.setEasingCurve(QEasingCurve.OutCubic)
            a2 = QPropertyAnimation(snap, b"geometry", snap)
            g0 = self.stack.rect()
            g1 = g0.adjusted(-14, -10, 14, 10)
            a2.setDuration(210)
            a2.setStartValue(g0)
            a2.setEndValue(g1)
            a2.setEasingCurve(QEasingCurve.OutCubic)
            a1.finished.connect(lambda: self._drop_snap(snap))
            a1.start()
            a2.start()
            #  硬兜底：动画被打断/特效对象提前释放时，快照也必须消失
            #   （否则那张不透明的旧页面位图会一直盖在新页面上 = 「背景被遮挡」）
            QTimer.singleShot(470, lambda: self._drop_snap(snap))
            self._page_anim = (a1, a2)
        except Exception:
            self.stack.setCurrentWidget(w)
        try:
            _make_transparent(w)     # 切到该页时再兜一次（页面可能刚被刷新/重建过）
        except Exception:
            pass
        _ulog(f"切页 → {key}（快照过渡，470ms 内必删）")
        for k, b in self.nav_btns.items():
            b.setChecked(k == key)
        # 状态定时器只在总览页跑（省 CPU）
        try:
            home = self.pages.get("home")
            if home is None:
                home = self._ensure_page("home")
            if key == "home":
                home._timer.start(6000)
                home.refresh_status()
            elif home is not None:
                home._timer.stop()
        except Exception:
            pass

    # ── 效果 ──
    def _on_video_frame(self, qimg):
        """把视频帧画到底板上（和图片壁纸走同一条路：底板 + 透明度）。"""
        try:
            from PyQt5.QtGui import QPixmap
            self.back.set_bg(QPixmap.fromImage(qimg))
            self.back.lower()
            self.back.update()
        except Exception as e:
            print(f"[NewUI] ⚠ 绘制视频帧失败: {e}")

    def _apply_effects(self):
        #  视频背景：必须保持「不透明窗口」（原生视频表面在透明窗口里不渲染），
        #   所以这里直接跳过亚克力/圆角那套透明窗口处理（用户反馈"视频背景不显示"）。
        try:
            if getattr(self, "_bg_widget", None) is not None:
                self.setAttribute(Qt.WA_TranslucentBackground, False)
                print("[NewUI] 当前是视频背景 → 跳过亚克力/圆角（保持不透明，视频才能显示）")
                return
        except Exception:
            pass
        # ui_acrylic=false 时跳过亚克力（低配/远程桌面下更流畅）
        try:
            import json as _json
            _cfg = _json.load(open(os.path.join(_app_base_dir(), "config.json"), encoding="utf-8"))
            if str(_cfg.get("ui_acrylic", "true")).strip().lower() in ("false", "0", "off", "no"):
                # 关掉亚克力（省性能）但依然要圆角 → 只做 DWM 圆角 + 透明窗口
                try:
                    self.setAttribute(Qt.WA_TranslucentBackground, True)
                    silicon_ui.apply_round_corners(self)
                    self.update()
                except Exception as _e:
                    print(f"[NewUI]  圆角设置失败: {_e}")
                print("[NewUI] 亚克力已关闭（保留圆角，更流畅）")
                return
        except Exception:
            pass
        try:
            silicon_ui.apply_acrylic(self)
            print("[NewUI] 亚克力 + 圆角已启用")
        except Exception as e:
            print(f"[NewUI]  亚克力失败: {e}")

    def _schedule_blur_refresh(self, delay_ms: int = 400):
        """停手后再做一次（带模糊的）完整重载 —— 重活只做一次"""
        try:
            from PyQt5.QtCore import QTimer
            self._bg_blur_timer = getattr(self, "_bg_blur_timer", None)
            if self._bg_blur_timer is None:
                self._bg_blur_timer = QTimer(self)
                self._bg_blur_timer.setSingleShot(True)
                self._bg_blur_timer.timeout.connect(self._finish_blur_refresh)
            self._bg_blur_timer.start(int(delay_ms))
        except Exception as e:
            print(f"[NewUI]  模糊刷新调度失败: {e}")

    def _finish_blur_refresh(self):
        self._bg_blur_skip = False
        self.reload_background()

    def apply_text_color(self, hexv: str = ""):
        """文字颜色即时生效：写盘后走「实时换肤」路径（重算色板 + 重建当前页）。"""
        try:
            from .themes_panel import _load_config, _save_config
            cfg = _load_config() or {}
            cfg["ui_text_color"] = str(hexv or "")
            _save_config(cfg)
        except Exception as e:
            print(f"[NewUI]  文字颜色写盘失败: {e}")
        try:
            from .colors import current_theme_id as _ctid
            self.apply_theme_live(_ctid(), persist=False)
            print(f"[NewUI] 文字颜色已实时应用: {hexv or '自动'}")
        except Exception as e:
            print(f"[NewUI]  文字颜色实时应用失败（重启启动器后生效）: {e}")

    def apply_bg_settings(self, values: dict):
        """实时应用背景设置（内存生效、不写盘；滑块拖动时调用 → 丝滑不卡）

        节流：50ms 内的重复调用直接忽略（拖动会产生大量回调）。"""
        try:
            import time as _t
            self._bg_live = getattr(self, "_bg_live", {})
            self._bg_live.update({k: v for k, v in (values or {}).items()})
            now = _t.time()
            if now - getattr(self, "_bg_last_ts", 0) < 0.05:
                # 值已记录，等下一次回调再重建（避免每像素都重算模糊）
                try:
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(60, self.reload_background)
                except Exception:
                    pass
                return
            self._bg_last_ts = now
            # 二级窗口（立绘工坊/新建桌宠…）实时跟随启动器底色
            try:
                if "ui_bg_color" in (values or {}):
                    from .silicon_dialog import refresh_all_dialog_colors
                    refresh_all_dialog_colors(values.get("ui_bg_color"))
            except Exception as _e:
                print(f"[NewUI]  同步二级窗口底色失败: {_e}")
            self._bg_blur_skip = True      # 拖动中：先不做模糊（毫秒级响应）
            # ★ 视频背景：透明度/模糊直接推给解码线程（下一帧生效），
            #   不要 reload —— 那会把播放器停掉重建，画面会闪、还会从头播。
            try:
                _vb = getattr(self, "_video_bg", None)
                if _vb is not None and set((values or {}).keys()) <= {"ui_bg_opacity", "ui_bg_blur"}:
                    _vb.set_effects(
                        opacity=(float(self._bg_value("ui_bg_opacity", 100) or 100) / 100.0),
                        blur=int(self._bg_value("ui_bg_blur", 0) or 0))
                    return
            except Exception as _e:
                print(f"[NewUI] ⚠ 视频背景参数更新失败: {_e}")
            self.reload_background()
            self._schedule_blur_refresh(400)   # 停手后补上模糊
        except Exception as e:
            print(f"[NewUI]  实时应用背景设置失败: {e}")

    def _bg_value(self, key: str, default):
        """优先取内存实时值（滑块拖动中），其次 config.json"""
        try:
            live = getattr(self, "_bg_live", {})
            if key in live:
                return live[key]
        except Exception:
            pass
        try:
            import json as _json
            cfg = _json.load(open(os.path.join(_app_base_dir(), "config.json"), encoding="utf-8"))
            v = cfg.get(key)
            return default if v in (None, "") else v
        except Exception:
            return default

    def reload_background(self):
        """实时重建主题背景（透明度/模糊度滑块拖动即生效，无需重启）"""
        try:
            if self._media is not None:
                try:
                    self._media.stop()
                except Exception:
                    pass
                self._media = None
            if self._bg_widget is not None:
                try:
                    self._bg_widget.hide()
                    self._bg_widget.deleteLater()
                except Exception:
                    pass
                self._bg_widget = None
            self._load_background()
            print("[NewUI] 背景已按新参数重建（实时生效）")
        except Exception as e:
            print(f"[NewUI]  背景重建失败: {e}")

    def _load_background(self):
        """主题背景（图片/视频）：铺满整窗，内容叠在上面"""
        try:
            # 背景底色：壁纸半透明时透出来的那层（config.ui_bg_color，默认黑）
            try:
                _bc = str(self._bg_value("ui_bg_color", "#000000") or "#000000").strip()
                if _bc:
                    self._set_base_color(QColor(_bc))
            except Exception:
                pass
            btype, src, opacity = background_info()
            # 用户在主题页可调：背景透明度 / 模糊度
            try:
                _o = self._bg_value("ui_bg_opacity", 100)
                if _o not in (None, ""):
                    opacity = max(0.05, min(1.0, float(_o) / 100.0))
                self._bg_blur = int(self._bg_value("ui_bg_blur", 0) or 0)
            except Exception:
                self._bg_blur = 0
            if not src:
                return
            if btype == "image":
                # 不建独立控件：壁纸交给圆角底板绘制（这样四角才是圆的）
                self._bg_widget = None
                _cache = getattr(self, "_bg_src_cache", None)
                if _cache is not None and _cache[0] == src:
                    pm = QPixmap(_cache[1])          # 用缓存，免去重复读盘/解码
                else:
                    pm = QPixmap(src)
                    try:
                        self._bg_src_cache = (src, pm)
                    except Exception:
                        pass
                if pm.isNull():
                    return
                # 预乘透明度（一次性绘制）—— 比 QGraphicsOpacityEffect 快很多
                # 散开的模糊：三趟盒式模糊 ≈ 高斯。
                # 拖动调节时先跳过（模糊较重），停手 400ms 后再补一次 → 拖动丝滑
                if getattr(self, "_bg_blur", 0) > 0 and not getattr(self, "_bg_blur_skip", False):
                    pm = _soft_blur(pm, int(self._bg_blur))
                if opacity < 0.99:
                    faded = QPixmap(pm.size())
                    faded.fill(Qt.transparent)
                    p = QPainter(faded)
                    p.setOpacity(max(0.05, min(1.0, float(opacity))))
                    p.drawPixmap(0, 0, pm)
                    p.end()
                    pm = faded
                try:
                    self.back.set_bg(pm)
                    self.back.lower()          # 底板在最底层（内容叠在上面）
                    self.back.update()
                except Exception as _e:
                    print(f"[NewUI]  设置圆角壁纸失败: {_e}")
            elif btype == "video":
                # ★ 用 cv2 逐帧解码，画到底板上（和图片壁纸同一条路）。
                #   为什么不用 QMediaPlayer：这台机器上 Qt 的多媒体后端
                #   （wmfengine / dsengine）打不开**完全标准**的 H.264 1080p mp4
                #   （实测 error=1 ResourceError、mediaStatus=InvalidMedia），
                #   视频背景就永远不显示（用户反馈）。cv2 自己解码不依赖系统解码器，
                #   同时绕开了「中文路径打不开」和「透明窗口装不下原生视频表面」两个坑。
                try:
                    self._video_bg = _VideoBgPlayer(_ascii_media_path(src), fps_cap=12.0, parent=self)
                    self._video_bg.set_effects(
                        opacity=(float(self._bg_value("ui_bg_opacity", 100) or 100) / 100.0),
                        blur=int(self._bg_value("ui_bg_blur", 0) or 0))
                    self._video_bg.frame_ready.connect(self._on_video_frame)
                    self._video_bg.start()
                    print(f"[NewUI] 主题背景视频（cv2 解码）: {os.path.basename(src)}")
                except Exception as _e:
                    print(f"[NewUI] ⚠ 视频背景启动失败: {_e}")
                return
        except Exception as e:
            print(f"[NewUI]  主题背景加载失败: {e}")

    def reload_background(self):
        """背景透明度/模糊度实时生效：销毁旧背景图/视频 → 按当前 config 重建"""
        try:
            if self._media is not None:
                try:
                    self._media.stop()
                except Exception:
                    pass
                self._media = None
            if self._bg_widget is not None:
                self._bg_widget.hide()
                self._bg_widget.deleteLater()
                self._bg_widget = None
            if getattr(self, "_video_bg", None) is not None:
                try:
                    self._video_bg.stop(); self._video_bg.wait(1500)
                except Exception:
                    pass
                self._video_bg = None
            self._load_background()
            print("[NewUI] 背景已按新设置重新加载")
        except Exception as e:
            print(f"[NewUI]  重载背景失败: {e}")

    def resizeEvent(self, event):
        try:
            if self._bg_widget is not None:
                self._bg_widget.setGeometry(0, 0, self.back.width(), self.back.height())
        except Exception:
            pass
        if event is not None:
            super().resizeEvent(event)

    def _set_base_color(self, color: QColor):
        """设置窗口底色（壁纸半透明时透出来的那一层）"""
        try:
            self._base_color = color
            self.back.set_color(color)
            self.back.update()
        except Exception as e:
            print(f"[NewUI]  设置底色失败: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        if self._silicon and not getattr(self, "_fx_done", False):
            self._fx_done = True
            QTimer.singleShot(50, self._apply_effects)
        # 预热页面：只提前建「便宜」的几页（几十毫秒），重的页面（插件 659ms / 记忆 321ms）
        # 改成鼠标悬停到对应导航按钮上再建 —— 以前一开机就挨个建，每建一个界面就卡一下
        # （用户反馈"每次打开都会卡一下"）。
        if not getattr(self, "_prewarm_started", False):
            self._prewarm_started = True
            self._prewarm_queue = ["settings", "pets", "prompt", "themes"]
            QTimer.singleShot(3000, self._prewarm_next)

    def _prewarm_page(self, key: str, why: str = "悬停"):
        """把某一页提前建好（点了才建的话第一次点会停顿）"""
        try:
            if key in self.pages or key in getattr(self, "_prewarm_busy", set()):
                return
            busy = getattr(self, "_prewarm_busy", None)
            if busy is None:
                busy = self._prewarm_busy = set()
            busy.add(key)
            import time as _t
            t0 = _t.time()
            self._ensure_page(key)
            print(f"[NewUI] 预热 {key}（{why}）: {(_t.time() - t0) * 1000:.0f}ms")
        except Exception as e:
            print(f"[NewUI]  预热 {key} 失败: {e}")
        finally:
            try:
                self._prewarm_busy.discard(key)
            except Exception:
                pass

    def eventFilter(self, obj, event):
        """导航按钮悬停 → 提前建对应页面（悬停时那一小下停顿，比开机乱卡自然）"""
        try:
            if event.type() == QEvent.Enter:
                key = getattr(obj, "_page_key", None)
                if key:
                    QTimer.singleShot(0, lambda k=key: self._prewarm_page(k))
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _prewarm_next(self):
        """逐个预热便宜页面（每个之间留 1200ms，绝不连着卡）"""
        try:
            q = getattr(self, "_prewarm_queue", [])
            if not q:
                return
            key = q.pop(0)
            self._prewarm_page(key, "空闲预热")
            QTimer.singleShot(1200, self._prewarm_next)
        except Exception as e:
            print(f"[NewUI]  预热失败: {e}")

    # ── 关闭清理 ──
    def closeEvent(self, event):
        """先隐藏窗口，再清理子进程。

         原来是"边关边杀"：taskkill / netstat / tasklist 都是同步调用，每个几百毫秒，
          点关闭要等一秒多才消失（用户反馈"关闭时卡一下"）。
          现在先把窗口藏掉（肉眼上立刻关掉），清理放到后台线程里做，最多等 1.5 秒再退出，
          用户已经看不到窗口了，感知上就是秒关。
        """
        procs = []
        try:
            procs = [p for p in (self._qq_proc, self._wx_proc) if p and p.poll() is None]
        except Exception:
            procs = []

        #  hide() 之前绝对不能有联网/子进程调用：
        #   _pet_api_alive() 要发 HTTP，桌宠没在跑时能卡好几秒 —— 那正是"关闭卡一下"的真凶。
        try:
            self.hide()
        except Exception:
            pass
        if self._media is not None:
            try:
                self._media.stop()
            except Exception:
                pass
        if getattr(self, "_video_bg", None) is not None:
            try:
                self._video_bg.stop()
            except Exception:
                pass
            self._video_bg = None

        def _cleanup():
            # 桌宠不在跑了才收视觉服务（这个判断要发 HTTP，放后台做）
            need_vision_kill = False
            try:
                need_vision_kill = not _pet_api_alive()
            except Exception:
                need_vision_kill = False
            for proc in procs:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except Exception:
                    pass
            if need_vision_kill:
                try:
                    stop_vision_service(self.shell)     # 桌宠没在跑就把视觉服务也收掉
                except Exception:
                    pass

        try:
            import threading as _th
            t = _th.Thread(target=_cleanup, daemon=True)
            t.start()
            t.join(1.5)          # 给清理一点时间（窗口已经藏了，用户感知不到）
        except Exception:
            _cleanup()
        event.accept()
        print("[NewUI] 启动器已关闭")


def _models_info() -> dict:
    """总览页「模型状态」用：语言模型 / 视觉模型 各自的名字、来源、要不要查余额。

    - 本地部署的（Ollama / 本地视觉模型）→ 只显示"本地部署"，不花钱
    - 云端的 → 显示模型名 + 去服务商查余额
    """
    cfg = _vision_cfg()          # 就是读 config.json（下面这些键都在里面）
    out = {}
    # ── 语言模型（对话）──
    mt = str(cfg.get("model_type") or "deepseek").strip().lower()
    _lt = str(cfg.get("longtext_enabled", "true")).strip().lower() in ("true", "1", "yes", "on")
    name = str((cfg.get("longtext_model_name") if _lt else cfg.get("short_model_name"))
               or cfg.get("short_model_name") or cfg.get("longtext_model_name") or "未配置").strip()
    key = str(((cfg.get("APIKEY") or {}).get(mt)) or "").strip()
    if mt == "local":
        out["lang"] = {"model": f"{name}（本地部署）", "balance": "本地部署，无费用", "provider": "local"}
    else:
        prov = {"deepseek": "DeepSeek", "qwen": "通义千问"}.get(mt, mt)
        out["lang"] = {"model": f"{name}（{prov} 云端）", "balance": None,
                       "provider": mt, "key": key}
    # ── 视觉模型（屏幕/摄像头识别）──
    if str(cfg.get("vision_source") or "local").strip().lower() == "local":
        d = str(cfg.get("vision_local_model_dir") or "").strip()
        base = os.path.basename(d.rstrip("\\/")) if d else ""
        out["vision"] = {"model": f"{base or '本地视觉模型'}（本地部署）",
                         "balance": "本地部署，无费用", "provider": "local"}
    else:
        vn = str(cfg.get("vision_model_name") or "未配置").strip()
        vkey = str(((cfg.get("APIKEY") or {}).get("qwen")) or "").strip()
        out["vision"] = {"model": f"{vn}（云端）", "balance": None,
                         "provider": "qwen", "key": vkey}
    return out


def _http_get_json(url: str, headers: dict, timeout: float = 8.0):
    """GET 一个 JSON：先按系统代理，失败再直连（和桌宠那边的网络策略一致）。"""
    import json as _json
    import urllib.request as _ur
    req = _ur.Request(url, headers=headers)
    last = None
    for use_proxy in (True, False):
        try:
            if use_proxy:
                op = _ur.build_opener()
            else:
                op = _ur.build_opener(_ur.ProxyHandler({}))   # 直连
            with op.open(req, timeout=timeout) as r:
                return _json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            last = e
    raise last if last else RuntimeError("请求失败")


def _deepseek_balance(api_key: str) -> str:
    """查 DeepSeek 余额 → '¥12.34'；查不到给一句能看懂的话。"""
    if not api_key:
        return "未填 API Key"
    try:
        d = _http_get_json("https://api.deepseek.com/user/balance",
                           {"Authorization": "Bearer " + api_key, "Accept": "application/json"})
        infos = d.get("balance_infos") or []
        if infos:
            it = infos[0]
            sym = {"CNY": "¥", "USD": "$"}.get(str(it.get("currency") or "CNY").upper(), "")
            return f"{sym}{it.get('total_balance')}"
        if d.get("is_available") is False:
            return "余额不足"
        return "—"
    except Exception as e:
        print(f"[NewUI]  DeepSeek 余额查询失败: {type(e).__name__}: {e}")
        return "查询失败（网络？）"


def _qwen_balance(api_key: str) -> str:
    """通义千问（阿里云 DashScope）没有公开的余额接口 → 说明一句，引导去控制台看。"""
    return "阿里云无余额接口，控制台查看" if api_key else "未填 API Key"


def _balance_for(provider: str, key: str) -> str:
    if provider == "local":
        return "本地部署，无费用"
    if provider == "deepseek":
        return _deepseek_balance(key)
    if provider == "qwen":
        return _qwen_balance(key)
    return "—"


def _vision_cfg() -> dict:
    """读 config.json：视觉识别走本地还是云端、本地服务端口是多少"""
    try:
        import json as _json
        with open(os.path.join(_app_base_dir(), "config.json"), encoding="utf-8") as f:
            return _json.load(f) or {}
    except Exception:
        return {}


def _vision_port(cfg: dict) -> int:
    """从 local_api.vision 里抠端口；没写就用 vision_local_port，再不行 28460"""
    u = str((cfg.get("local_api") or {}).get("vision") or "")
    m = re.search(r":([0-9]+)", u)
    if m:
        return int(m.group(1))
    try:
        return int(cfg.get("vision_local_port") or 28460)
    except Exception:
        return 28460


def _vision_alive(port: int) -> bool:
    import socket as _s
    try:
        with _s.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except Exception:
        return False


def ensure_vision_service(shell) -> bool:
    """按设置拉起本地视觉服务（tool/vision_service.py，借用 GPT-SoVITS 的 ROCm 运行时 + 显卡）。

    - 设置里选了「云端 API」→ 不启动
    - 服务已经在跑（比如上一次没关干净）→ 不重复启动
    - 找不到运行时/模型 → 只打日志，桌宠那边会自动回落到云端
    """
    cfg = _vision_cfg()
    if str(cfg.get("vision_source") or "local").strip().lower() != "local":
        print("[NewUI] 视觉识别设为云端 API，本地视觉服务不启动")
        return False
    port = _vision_port(cfg)
    if _vision_alive(port):
        print(f"[NewUI] 本地视觉服务已在运行（端口 {port}）")
        return True
    base = _app_base_dir()
    script = os.path.join(base, "tool", "vision_service.py")
    if not os.path.isfile(script):
        print("[NewUI]  缺少 tool/vision_service.py，跳过本地视觉服务")
        return False
    py = ""
    try:
        # 统一的「用哪个 python」规则：配置指定的（安装时配置写进去的）→ GPT-SoVITS 整合包
        # → <程序目录>/vision_runtime → 本体 venv。优先挑带显卡加速的那个。
        from tool import vision_setup as _vs
        py = _vs.find_gpu_runtime(base, cfg) or ""
        if not py:
            _cand = _vs.find_runtime(base, cfg)
            if _cand and _vs._has_torch(_cand):
                py = _cand
                print("[NewUI]  没找到带显卡加速的运行时，用现有的（识别会明显变慢）")
    except Exception as e:
        print(f"[NewUI]  视觉运行时探测失败，按老规矩找：{e}")
    if not py:
        for rel in (os.path.join("GPT-SoVITS", "runtime_rocm", "Scripts", "python.exe"),
                    os.path.join("GPT-SoVITS", "runtime", "Scripts", "python.exe"),
                    os.path.join("GPT-SoVITS", "runtime", "python.exe"),
                    os.path.join("vision_runtime", "Scripts", "python.exe")):
            if os.path.isfile(os.path.join(base, rel)):
                py = os.path.join(base, rel)
                break
    if not py:
        print("[NewUI]  没找到能跑视觉模型的运行时"
              "（装 GPT-SoVITS 整合包，或到设置里把识别来源改成云端 API）")
        return False
    try:
        os.makedirs(os.path.join(base, "data"), exist_ok=True)
        log = open(os.path.join(base, "data", "vision_service.log"), "a",
                   encoding="utf-8", errors="replace")
    except Exception:
        log = None
    try:
        shell._vision_proc = subprocess.Popen(
            [py, script], cwd=base, stdout=log, stderr=subprocess.STDOUT,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        print(f"[NewUI] 已启动本地视觉服务（PID {shell._vision_proc.pid}，日志 data/vision_service.log）")
        return True
    except Exception as e:
        print(f"[NewUI]  启动本地视觉服务失败: {e}")
        return False


def _vision_pid_on_port(port: int) -> int:
    """谁占着这个端口（服务不是本启动器拉起来的时，也得能收掉它）。

    只认 python 进程 —— 万一这个端口被别的程序占了，不能去杀人家。
    """
    try:
        # 注意：中文 Windows 的 netstat/tasklist 输出是 GBK，不能直接 text=True
        out = (subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
               or b"").decode("utf-8", "replace")
    except Exception:
        return 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4 or not parts[1].endswith(":" + str(port)):
            continue
        if "LISTENING" not in line.upper():
            continue
        try:
            pid = int(parts[-1])
        except Exception:
            continue
        try:
            chk = (subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                   or b"").decode("utf-8", "replace")
        except Exception:
            return 0
        if "python" in chk.lower():
            return pid
    return 0


def stop_vision_service(shell):
    """收掉本地视觉服务：它一直占着显卡，桌宠不用了就该让出来"""
    proc = getattr(shell, "_vision_proc", None)
    try:
        shell._vision_proc = None
    except Exception:
        pass
    pid = proc.pid if (proc and proc.poll() is None) else _vision_pid_on_port(_vision_port(_vision_cfg()))
    if not pid:
        return
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print(f"[NewUI] 本地视觉服务已关闭（PID {pid}）")
    except Exception as e:
        print(f"[NewUI]  关闭本地视觉服务失败: {e}")


def _ulog(msg: str):
    """外壳关键事件写文件（冻结版没有控制台 → 出问题只能靠日志定位）"""
    try:
        import time as _t
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        d = os.path.join(base, "tmp")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "launcher_ui.log"), "a", encoding="utf-8") as f:
            f.write(f"[{_t.strftime('%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _hook_repaint_transparency(page):
    """页面内容会被重建（刷新桌宠列表 / 重扫插件）→ 重建后再次透明化，
    否则新建出来的卡片带回不透明背景，又把主题壁纸挡住（打开向导后复现的那个问题）。"""
    targets = [page]
    try:
        targets += [w for w in page.findChildren(QWidget) if w is not page]
    except Exception:
        pass
    for tgt in targets:
        for name in ("_refresh", "_reload"):
            fn = getattr(tgt, name, None)
            if not callable(fn) or getattr(fn, "_silicon_hooked", False):
                continue
            try:
                def _wrap(orig, owner=tgt, mname=name):
                    def _inner(*a, **kw):
                        r = orig(*a, **kw)
                        try:
                            _make_transparent(owner)          # 立即
                            from PyQt5.QtCore import QTimer   # Qt 可能晚一步重建 → 再补两次
                            QTimer.singleShot(150, lambda: _make_transparent(owner))
                            QTimer.singleShot(450, lambda: _make_transparent(owner))
                            _ulog(f"{owner.__class__.__name__}.{mname} → 已重新透明化（防止卡片遮挡背景）")
                        except Exception:
                            pass
                        return r
                    _inner._silicon_hooked = True
                    return _inner
                setattr(tgt, name, _wrap(fn))
                print(f"[NewUI] 已挂钩 {tgt.__class__.__name__}.{name}（重建后自动透明化）")
                _ulog(f"已挂钩 {tgt.__class__.__name__}.{name}（刷新后自动透明化）")
            except Exception as e:
                print(f"[NewUI]  挂钩 {name} 失败: {e}")


def _soft_blur(pm: QPixmap, strength: int) -> QPixmap:
    """三趟盒式模糊（分离式，numpy 加速）→ 近似高斯的「散开」效果。

    strength 0~100 → 半径 2~48 像素。找不到 numpy 时回退到缩放模糊。
    """
    try:
        r = max(2, int(strength * 0.48))
        img = pm.toImage().convertToFormat(4)          # QImage.Format_RGB32
        w, h = img.width(), img.height()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        import numpy as np
        a = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).astype(np.float32)

        def _box(arr, rad):
            # 分离式盒式模糊（横向 + 纵向），用累积和做 O(n)
            if rad < 1:
                return arr
            k = 2 * rad + 1
            pad = np.pad(arr, ((0, 0), (rad, rad), (0, 0)), mode="edge")
            cs = np.cumsum(pad, axis=1)
            cs = np.concatenate([np.zeros((h, 1, 4), np.float32), cs], axis=1)
            arr = (cs[:, k:, :] - cs[:, :-k, :]) / k
            pad = np.pad(arr, ((rad, rad), (0, 0), (0, 0)), mode="edge")
            cs = np.cumsum(pad, axis=0)
            cs = np.concatenate([np.zeros((1, w, 4), np.float32), cs], axis=0)
            return (cs[k:, :, :] - cs[:-k, :, :]) / k

        for _ in range(3):                             # 三趟 ≈ 高斯
            a = _box(a, max(1, r // 3))
        out = np.clip(a, 0, 255).astype(np.uint8)
        out.setflags(write=True)
        qimg = QImage(out.data, w, h, w * 4, 4)
        return QPixmap.fromImage(qimg.copy())
    except Exception as e:
        print(f"[NewUI]  高斯模糊不可用，回退缩放模糊: {e}")
        try:
            f = max(2, int(strength) // 6 + 1)
            small = pm.scaled(max(1, pm.width() // f), max(1, pm.height() // f),
                              Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            return small.scaled(pm.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        except Exception:
            return pm


def _make_transparent(root_widget, alpha: float = 0.35, recurse: bool = True):
    """把控件树里的实心背景改成半透明，让主题壁纸透出来。

    - 只改「有实心背景色」的内联样式（#rrggbb / rgb(...) / 主题色名），改成同色 + 透明度
    - 纯 transparent / rgba 保持不变；QScrollArea 的视口一并处理，避免白/黑块遮挡
    - 只做一次（页面构建时调用），运行时零开销
    """
    try:
        root_widget.setAutoFillBackground(False)
    except Exception:
        pass

    hex_re = re.compile(r"(background(?:-color)?\s*:\s*)(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|rgba?\([^)]*\))")

    def _translucent(css: str) -> str:
        def _rep(m):
            head, col = m.group(1), m.group(2)
            try:
                if col.startswith("#"):
                    c = QColor(col)
                else:
                    parts = col[col.find("(") + 1:col.rfind(")")].split(",")
                    nums = [int(float(x.strip())) for x in parts]
                    if len(parts) == 4 and nums[3] <= 1:      # rgba 已带透明度 → 不动
                        return m.group(0)
                    c = QColor(nums[0], nums[1], nums[2])
                if not c.isValid():
                    return m.group(0)
                return f"{head}rgba({c.red()},{c.green()},{c.blue()},{int(alpha * 255)})"
            except Exception:
                return m.group(0)
        return hex_re.sub(_rep, css)

    widgets = [root_widget] + (root_widget.findChildren(QWidget) if recurse else [])
    for child in widgets:
        try:
            child.setAutoFillBackground(False)
            css = child.styleSheet()
            if css and "background" in css:
                child.setStyleSheet(_translucent(css))
            # 滚动区视口 / 列表视口：透明
            if isinstance(child, QScrollArea):
                vp = child.viewport()
                if vp is not None:
                    vp.setAutoFillBackground(False)
                    vp.setStyleSheet("background: transparent;")
        except Exception:
            pass


class _RoundBack(QWidget):
    """启动器自己的底色层：圆角 + 竖向渐变。

    壁纸（背景图/视频）以「背景透明度」叠在它上面 → 半透明时透出下层底色，
    因为底色是渐变，所以整体呈现出渐变＋壁纸的混合观感（这就是「启动器底色」的作用）。
    底色可调：config.ui_bg_color（默认 #000000 黑）。
    """

    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color

    def set_color(self, c: QColor):
        self._color = c
        self.update()

    def set_bg(self, pixmap):
        """设置壁纸（已含透明度/模糊处理）→ 与渐变底色一起在圆角内绘制"""
        self._bg = pixmap
        self.update()

    def rounded_path(self):
        path = QPainterPath()
        r = silicon_ui.M.radius_win
        path.addRoundedRect(0, 0, self.width(), self.height(), r, r)
        return path

    def paintEvent(self, event):
        try:
            from PyQt5.QtGui import QLinearGradient
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            r = silicon_ui.M.radius_win
            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), r, r)
            c = QColor(self._color)
            top = c.lighter(150)          # 上浅
            bottom = c.darker(135)        # 下深 → 形成柔和渐变
            grad = QLinearGradient(0, 0, 0, max(1, self.height()))
            grad.setColorAt(0.0, top)
            grad.setColorAt(0.55, c)
            grad.setColorAt(1.0, bottom)
            p.fillPath(path, grad)
            # 壁纸也画在圆角里（关键：否则方形的壁纸会把四个角盖成直角）
            bg = getattr(self, "_bg", None)
            if bg is not None and not bg.isNull():
                p.save()
                p.setClipPath(path)
                # 按窗口尺寸铺满（保持比例裁剪，避免拉伸变形）
                sc = bg.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                               Qt.SmoothTransformation)
                x = (self.width() - sc.width()) // 2
                y = (self.height() - sc.height()) // 2
                p.drawPixmap(x, y, sc)
                p.restore()
            p.end()
        except Exception:
            try:
                p = QPainter(self)
                p.fillRect(self.rect(), self._color)
                p.end()
            except Exception:
                pass


def _opacity_effect(opacity: float):
    eff = QGraphicsOpacityEffect()
    try:
        eff.setOpacity(max(0.05, min(1.0, float(opacity))))
    except Exception:
        eff.setOpacity(1.0)
    return eff


class SplashScreen(QWidget):
    """开屏动画：图标 + 名称 + 进度条，淡入 → 主窗就绪后淡出"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(420, 240)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        card = _RoundBack(QColor(Color8))
        card.setStyleSheet(
            f"QWidget {{ border: 1px solid {Color5.name()};"
            f" border-radius: {silicon_ui.M.radius_card}px; }}")
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(10)

        ico = QLabel()
        p = os.path.join(_app_base_dir(), "icon.png")
        if os.path.exists(p):
            pm = QPixmap(p)
            if not pm.isNull():
                ico.setPixmap(pm.scaled(84, 84, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("border: none; background: transparent;")
        lay.addWidget(ico)

        t = QLabel("AIpet 丛雨桌宠")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"color: {Color1.name()}; font-size: 20px; font-weight: bold;"
                        f" font-family: '{silicon_ui.M.font}'; border: none; background: transparent;")
        lay.addWidget(t)

        sub = QLabel("正在启动…")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color: {Gray2.name()}; font-size: 12px; border: none;")
        self._sub = sub
        lay.addWidget(sub)

        from PyQt5.QtWidgets import QProgressBar
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(8)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        acc = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")
        bar.setStyleSheet(
            f"QProgressBar {{ background: rgba(255,255,255,0.12); border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {acc}; border-radius: 3px; }}")
        lay.addWidget(bar)
        self._bar = bar

        # 居中 + 淡入
        from PyQt5.QtWidgets import QApplication
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.center().y() - self.height() // 2)
        self.setWindowOpacity(0.0)

    def set_progress(self, v: int, text: str = ""):
        try:
            self._bar.setValue(max(0, min(100, int(v))))
            if text:
                self._sub.setText(text)
        except Exception:
            pass

    def fade(self, to: float, ms: int, then=None):
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(int(ms))
        a.setStartValue(self.windowOpacity())
        a.setEndValue(float(to))
        a.setEasingCurve(QEasingCurve.OutCubic)
        if then:
            a.finished.connect(then)
        a.start(QPropertyAnimation.DeleteWhenStopped)
        self._anim = a


def launch() -> int:
    """入口：启动新版启动器"""
    from PyQt5.QtWidgets import QApplication
    from . import silicon_ui as _sui
    from .colors import current_theme_id
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        from . import safety as _safety
        _safety.install("launcher")
    except Exception as _e:
        print(f"[NewUI]  全局异常兜底不可用: {_e}")
    if current_theme_id() == "silicon":
        _sui.install(app, accent=THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0"))
    #  不再用开屏窗口（原来那个 420x240 的小卡片就是用户看到的"弹窗"）：
    #   外壳构造实测只要 ~90ms，开屏纯属白等，还给启动过程加了 450ms 延迟和一次窗口切换。
    #   直接显示主窗 + 淡入，打开即见。
    win = SiliconLauncher()
    try:
        win.show()
        _fade_window_in(win)
    except Exception as e:
        print(f"[NewUI]  主窗显示失败（直接显示）: {e}")
        try:
            win.show()
        except Exception:
            pass
    return app.exec_()


def _fade_window_in(win):
    """主窗淡入（窗口级透明度动画，开销很小）"""
    try:
        from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
        win.setWindowOpacity(0.0)
        a = QPropertyAnimation(win, b"windowOpacity", win)
        a.setDuration(260)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.start(QPropertyAnimation.DeleteWhenStopped)
        win._fade_in_anim = a
    except Exception as e:
        print(f"[NewUI]  主窗淡入失败: {e}")
