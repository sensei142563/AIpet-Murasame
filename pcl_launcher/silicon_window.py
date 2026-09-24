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
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

from PyQt5.QtCore import Qt, QTimer, QSize, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import (QColor, QFont, QIcon, QImage, QPainter, QPainterPath,
                         QPixmap)
from PyQt5.QtWidgets import (QScrollArea, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QFrame, QSizePolicy)

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


_WALLPAPER_CACHE = {"v": None}


def _has_wallpaper() -> bool:
    """当前主题是否声明了背景（图片/视频）。带缓存：SF() 会被调用几百次，
    每次都去读 theme.json + config.json 太亏（启动变慢）。换主题时清缓存。"""
    if _WALLPAPER_CACHE["v"] is None:
        try:
            _bt, _src, _op = background_info()
            _WALLPAPER_CACHE["v"] = bool(_src)
        except Exception:
            _WALLPAPER_CACHE["v"] = False
    return bool(_WALLPAPER_CACHE["v"])


def _reset_style_caches():
    """换主题后调用（主题/壁纸变了，SF() 的结果跟着变）"""
    _WALLPAPER_CACHE["v"] = None


def SF(alpha: float) -> str:
    """面颜色（卡片/输入框/按钮底色）。

    · 没壁纸：深色主题=白透明 / 浅色主题=黑透明，0.02~0.30 → 露出底色渐变，层次感好
    · **有壁纸**：改用主题自己的面板色（Color6）+ 高不透明度（0.82~0.96）。
      卡片的职责是给文字一个稳定的底；壁纸一花，30% 的卡片约等于没有，文字直接糊在
      画面里 —— 这就是用户报的「千恋万花·樱华主题看不清字」（背景是角色拼贴画）。
      ⚠ 别用"黑/白 + 高 alpha"：浅色主题上黑 0.9 = 黑板（试过，整个界面会变黑）。
    """
    if _has_wallpaper():
        c = Color6
        a = min(0.96, 0.82 + 0.14 * min(1.0, max(0.0, alpha) / 0.30))
        return f"rgba({c.red()},{c.green()},{c.blue()},{a:.3f})"
    a = max(0.02, min(0.30, alpha))
    if _is_light_theme():
        return f"rgba(0,0,0,{a:.3f})"
    # 深色底：以前是"白 + 0.30"，在纯黑底上就是一块灰白卡片（用户反馈"卡片变白了"）→
    # 改用**派生面色** Color6（纯黑底时是 #191919）带透明度：卡片仍是深色，
    # 层级靠边框与这点微亮体现，跟主题/底色都一致。
    try:
        _c = Color6
        return f"rgba({_c.red()},{_c.green()},{_c.blue()},{min(0.92, 0.42 + a):.3f})"
    except Exception:
        return f"rgba(255,255,255,{a * 0.35:.3f})"


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
        print(f"[NewUI] ⚠ 程序目录加入导入路径失败: {e}")
    return False


# 各入口真正跑起来需要的模块（用来判断"系统 Python 装了没装依赖"）。
# 与三个 bat 的探针**同一套口径**（启动桌宠.bat / 启动QQ.bat / 启动微信.bat 里的 find_spec）：
#   桌宠 PyQt5+torch ／ QQ websocket+requests ／ 微信 requests+Crypto+qrcode
PET_NEED = ("PyQt5", "torch")
QQ_NEED = ("websocket", "requests")
WX_NEED = ("requests", "Crypto", "qrcode")


def _python_has(py: str, need=()) -> bool:
    """这个解释器能不能找到 need 里的模块（find_spec 只查不导入，毫秒级，不触发 DLL 加载）"""
    if not need:
        return True
    try:
        code = ("import importlib.util as u, sys;"
                "sys.exit(0 if all(u.find_spec(m) for m in %r) else 1)" % (list(need),))
        # 启动器是 windowed exe：不抑制控制台的话，探测时会闪黑框
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run([py, "-c", code], timeout=20,
                              creationflags=flags).returncode == 0
    except Exception:
        return False


def _find_python(base: str, need=()) -> str:
    """按顺序找能用的解释器；找不到返回空串（调用方给准确提示）。

    ⚠ 历史坑（用户 2026-09-24 实测）：这里原来只有下面 ①②，且打包版直接 `return ""`
      —— 而**它自己的报错文案写着"启动器需要 runtime\\venv 或系统 Python"**，
      三个 bat 也都会回落系统 Python（`set "PYTHON_CMD=python"` + 依赖探针）。
      于是同一个项目里"bat 能用系统 Python、exe 不能用"，打包版解压后点按钮就只会
      报"没找到 Python 解释器/未找到微信模块"，把人指向错误方向。现在补齐 ③：

      ① 包内运行环境 runtime\\venv（install.bat 建的，或自带）
      ② 包内便携解释器 python.exe
      ③ 系统 Python（PATH 上的 python / python3）—— **必须先过依赖探针**：
         "能启动、一跑就崩"比直接说清楚更糟
      ④ 源码模式：当前解释器（启动器自己跑得起来，说明它至少有 PyQt5）
    """
    for rel in (os.path.join("runtime", "venv", "Scripts", "python.exe"), "python.exe"):
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    if not getattr(sys, "frozen", False):
        # 源码模式：正在跑启动器的这个解释器就是它（别再另挑一个，避免和 .venv 打架）
        return sys.executable
    for name in ("python", "python3"):
        p = shutil.which(name)
        if p and _python_has(p, need):
            return p
    return ""


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
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _send_control(feature: str):
    try:
        req = urllib.request.Request(f"{_CONTROL_BASE}/{feature}", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=5) as r:
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
            print(f"[NewUI] ⚠ 主题导航图标加载失败({self._icon_key}): {e}")

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


# ══════════ 本地视觉服务（合并保留：开发板/桌宠的本地视觉靠它拉起）══════════
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


# ══════════ 模型余额 / 进程启动（合并保留：他版界面没有这些）══════════
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


def _balance_for(provider: str, key: str) -> str:
    if provider == "local":
        return "本地部署，无费用"
    if provider == "deepseek":
        return _deepseek_balance(key)
    if provider == "qwen":
        return _qwen_balance(key)
    return "—"


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
QPushButton:disabled {{ color: {Gray3.name()}; border-color: {Color5.name()}; }}
"""


def _switch_btn_qss(accent: str) -> str:
    """开关按钮样式：**看得出现在是开还是关**。

    首页的「长文本模式 / Live2D」其实是一次切换一次的开关，但原来用的是普通按钮样式，
    点完外观毫无变化 → 用户不知道当前是开还是关（这是首页最"不清晰"的地方）。
    这里 :checked 用强调色描边 + 淡强调底色，文字里也带上"开/关"（见 HomePage）。
    """
    a = QColor(accent)
    fill = f"rgba({a.red()},{a.green()},{a.blue()},0.18)"
    return f"""
QPushButton {{
    background: {SF(0.08)}; color: {Color1.name()};
    border: 1px solid {Color5.name()}; border-radius: 9px; padding: 9px 16px;
    font-size: 13px; font-family: "{silicon_ui.M.font}";
}}
QPushButton:hover {{ background: {SF(0.16)}; border-color: {Color3.name()}; }}
QPushButton:checked {{
    background: {fill}; color: {Color1.name()};
    border: 1px solid {accent}; font-weight: bold;
}}
QPushButton:checked:hover {{ background: {fill}; border-color: {accent}; }}
QPushButton:disabled {{ color: {Gray3.name()}; border-color: {Color5.name()}; }}
"""


def _hold_btn_qss(accent: str) -> str:
    """「按住说话」这类长按按钮：**按下时必须有明显变化**。

    原来按住没有任何视觉反馈，用户不知道有没有在录（桌宠那边其实会弹出"正在录音"，
    但启动器这侧一片安静）。这里按下时换成强调色实心 + 换文字（见 HomePage）。
    """
    a = QColor(accent)
    return f"""
QPushButton {{
    background: {SF(0.08)}; color: {Color1.name()};
    border: 1px solid {Color5.name()}; border-radius: 9px; padding: 9px 16px;
    font-size: 13px; font-family: "{silicon_ui.M.font}";
}}
QPushButton:hover {{ background: {SF(0.16)}; border-color: {Color3.name()}; }}
QPushButton:pressed {{
    background: {accent}; color: white; border: 1px solid {accent}; font-weight: bold;
}}
QPushButton:disabled {{ color: {Gray3.name()}; border-color: {Color5.name()}; }}
"""


# 拉起 NapCat 后最多等这么久（秒）。做成模块常量：测试要把它改小，不然每个用例
# 都得真等 75 秒（第一版把超时当参数注入，结果测试里没生效、工作线程串到下一个用例，
# 排查了半天——常量比"隐式参数"更好验证）。
NAPCAT_WAIT_S = 75


def _napcat_ws_port() -> int:
    """OneBot 正向 WS 端口（从 config 的 qq_napcat_ws 解析，默认 3001）"""
    try:
        from urllib.parse import urlparse
        with open(os.path.join(_app_base_dir(), "config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        u = urlparse(str(cfg.get("qq_napcat_ws") or "ws://127.0.0.1:3001"))
        return int(u.port or 3001)
    except Exception:
        return 3001


def _napcat_launcher_bat() -> str:
    """NapCat 的启动脚本（走注册表找到的 QQ，实测 9.9.22-40990 在 4.18.14 支持表内）。

    ⚠ 不用 start_napcat.bat：它用随包的绿色 QQ 9.9.33-51802，超出 NapCat 4.18.14 的
      支持表上限 9.9.32-50969，可能报"不支持当前QQ版本架构"。
    """
    return os.path.join(_app_base_dir(), "NapCat.Shell.Windows.OneKey", "NapCat",
                        "launcher-user.bat")


# ══════════════════════ 总览页 ══════════════════════
class HomePage(QWidget):
    """总览：启动/关闭桌宠、QQ、微信 + 控制面板 + 运行状态"""

    _probe_signal = pyqtSignal()
    _napcat_progress = pyqtSignal(str)             # 启动 NapCat 过程中的状态行文案
    _napcat_done = pyqtSignal(bool, str, str)      # (就绪?, 说明, 后续动作)
    _switch_done = pyqtSignal(str)                 # 换角色完成（角色显示名）
    _models_probe_signal = pyqtSignal()             # 模型余额查询结果回到界面线程

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
        # 活动角色名：首屏就带上（不然要等第一次状态刷新才有名字）
        _tag0 = f"（{self._active_pet_name()}）" if self._active_pet_name() else ""
        self.chip_pet = StatusChip(f"桌宠{_tag0}：未运行")
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
        # 按钮上直接写出"要启动哪一只"（活动角色在「桌宠」页切换）
        self.btn_pet = QPushButton(f"  启动 AIpet 桌宠{_tag0}")
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
        # ── 预载服务（合并保留：他版界面里没有这两个按钮）──────────────────
        # 预载语音服务：提前把 TTS 启动 + 预热好，之后再启动桌宠，第一句话不用等冷启动
        self.btn_preload = QPushButton("  预载语音服务")
        self.btn_preload.setStyleSheet(_ghost_btn_qss())
        self.btn_preload.setMinimumHeight(46)
        self.btn_preload.setToolTip(
            "提前启动并预热语音服务（GPT-SoVITS）：\n"
            "首次加载模型要 1~2 分钟，预热后桌宠开口几乎不用等。\n"
            "预载完成后按钮显示「预载完成」。")
        self.btn_preload.clicked.connect(self.preload_tts)
        # 预载视觉服务：本地视觉模型加载 + 预热约 30 秒
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

        # ── 控制面板卡片 ──
        ctl = Card()
        cl2 = QVBoxLayout(ctl)
        cl2.setContentsMargins(18, 14, 18, 16)
        cl2.setSpacing(10)
        cl2.addWidget(silicon_ui.section_title("桌宠控制面板", accent))
        grid = QHBoxLayout()
        for text, feat in (("长文本模式", "longtext"), ("Live2D", "live2d"),
                           ("摄像头识别", "camera"), ("屏幕识别", "screenshot"),
                           ("按住说话", "voice")):
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
        self.btn_reset_pos = QPushButton("重置桌宠位置")
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
        # 拉起 NapCat 的提示比较长（"…二维码在 NapCat 窗口里，也保存在 …\cache\qrcode.png"）
        # → 必须换行，否则被裁掉一半
        self.status_lbl.setWordWrap(True)
        cl2.addWidget(self.status_lbl)
        outer.addWidget(ctl)

        # ── 快捷工具卡片 ──
        tools = Card()
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(18, 14, 18, 16)
        tl.setSpacing(10)
        tl.addWidget(silicon_ui.section_title("快捷工具", accent))
        tr = QHBoxLayout()
        for text, slot in (("立绘工坊", self.open_studio),
                           ("桌宠设置", self.open_pet_settings),
                           ("NapCat WebUI", self.open_napcat_webui),
                           ("重新扫码登录", self.napcat_relogin),
                           ("打开程序目录", self.open_app_dir),
                           ("更新日志", self.open_changelog)):
            b = QPushButton(text)
            b.setStyleSheet(_ghost_btn_qss())
            b.clicked.connect(slot)
            if "NapCat WebUI" in text:
                self.btn_webui = b      # 拉起 NapCat 时要改它的文案/置灰（不能让局部变量带走）
            tr.addWidget(b)
        tr.addStretch()
        tl.addLayout(tr)
        # ── 剧情模式（Galgame）入口（合并保留）：程序目录里真有 story/ 与 剧情素材 才显示，
        #   正式版不含这两个目录 → 自动隐藏，免得点了报错 ──
        try:
            _has_story = all(os.path.isdir(os.path.join(_app_base_dir(), _d))
                             for _d in ("story", "剧情素材"))
        except Exception:
            _has_story = False
        if _has_story:
            sr = QHBoxLayout()
            b_story = QPushButton("剧情模式")
            b_story.setStyleSheet(_ghost_btn_qss())
            b_story.setToolTip("进入 Galgame 风格的剧情玩法（独立窗口）")
            b_story.clicked.connect(self._open_story)
            sr.addWidget(b_story)
            sr.addStretch()
            tl.addLayout(sr)
        else:
            print("[NewUI] 未包含剧情模块 → 隐藏「剧情模式」入口")
        outer.addWidget(tools)

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
        # ⚠ 必须真的把它加进布局 —— 旧版这句在文件末尾，合并时只搬了"创建卡片"那段，
        #   结果卡片建了却没挂上去 → 主页看不到（用户反馈"主页还是没有显示"）
        outer.addWidget(models)

        outer.addStretch()

        self._probe_signal.connect(self._apply_status)
        self._switch_done.connect(self._on_switch_done)
        # 拉起 NapCat 的过程文案（"正在检查 NapCat…"/"已在运行"/"正在等待扫码…"）打在状态行上；
        # 结束回调决定"继续启动 QQ / 打开 WebUI"还是"弹窗说明为什么没就绪"
        self._napcat_progress.connect(self.status_lbl.setText)
        self._napcat_done.connect(self._on_napcat_done)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(6000)

        # ── 启动器一起来就自动预热语音服务（合并保留的功能）────────────────
        # 首次加载 GPT-SoVITS 模型要 1~2 分钟；提前热好，桌宠开口第一句几乎不用等。
        # 和点「预载语音服务」走同一条路（preload_tts），只是不用手动点；
        # 云端语音 / 关掉短语音时不预热（判断见 _auto_preload_tts）。
        try:
            from PyQt5.QtCore import QTimer as _QT_pre
            _QT_pre.singleShot(2500, self._auto_preload_tts)
        except Exception as _e:
            print(f"[NewUI] ⚠ 自动预热未排上: {_e}")

    def _auto_preload_tts(self):
        """启动器启动后自动预热本地语音服务（只用本地 TTS 且开着短语音时才做）。"""
        try:
            if getattr(self.shell, "_tts_proc", None) is not None:
                print("[NewUI] 语音服务已在预载/运行 → 跳过自动预热")
                return
            from tool.config import get_config
            cfg = get_config("./config.json") or {}
            if str(cfg.get("tts_type") or "local").strip().lower() != "local":
                print("[NewUI] 语音走云端 → 跳过自动预热")
                return
            if str(cfg.get("voice_synthesis_enable", "true")).strip().lower() in (
                    "false", "0", "no", "off", "关"):
                print("[NewUI] 短语音已关闭 → 跳过自动预热")
                return
            print("[NewUI] 启动器自动预热语音服务（首次加载模型约 1~2 分钟）…")
            self.preload_tts()
        except Exception as e:
            print(f"[NewUI] ⚠ 自动预热跳过: {e}")

    # ── 状态 ──

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
                _vcfg = _vision_cfg()
                if str(_vcfg.get("vision_source") or "local").strip().lower() != "local":
                    vis_state = "cloud"
                else:
                    vis_state = "online" if _vision_alive(_vision_port(_vcfg)) else "offline"
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
            # 缓存给别的页面用（例如「桌宠」页卡片上那个按钮该写"设为活动"还是"切换到这个桌宠"）——
            # 卡片构建时不能自己发网络探测，否则一屏卡片能把界面卡住好几秒
            try:
                self.shell._pet_alive_cache = bool(alive)
            except Exception:
                pass
            # 桌宠名字带上：用户问过"怎么启动诺瓦？"——总览页得说清现在启的是哪一只
            # （活动角色在「桌宠」页用「⭐ 设为活动」切换；换角色后这里 6 秒内自动跟上）
            name = self._active_pet_name()
            tag = f"（{name}）" if name else ""
            self.chip_pet.set_text(f"桌宠{tag}：运行中" if alive else f"桌宠{tag}：未运行", alive)
            # 「正在关闭/启动中」期间不要被状态刷新覆盖文案
            if self.btn_pet.isEnabled():
                self.btn_pet.setText(f"关闭桌宠{tag}"if alive
                                     else f"  启动 AIpet 桌宠{tag}")
            accent = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#2f6fd0")
            self.btn_pet.setStyleSheet(_accent_btn_qss(accent, danger=alive))
            try:
                self.btn_reset_pos.setEnabled(alive)
                if self.btn_reset_pos.isEnabled():
                    self.btn_reset_pos.setText("重置桌宠位置")
            except Exception:
                pass
            qq_on = self.shell._qq_proc is not None and self.shell._qq_proc.poll() is None
            self.chip_qq.set_text("QQ：运行中" if qq_on else "QQ：未运行", qq_on)
            self.chip_tts.set_text("语音服务：在线" if tts_ok else "语音服务：未启动", tts_ok)
            _vis_txt = {"online": "视觉服务：在线", "offline": "视觉服务：未启动",
                        "cloud": "视觉服务：云端 API", "unknown": "视觉服务：未知"}.get(vis_state, "视觉服务：未知")
            self.chip_vision.set_text(_vis_txt, vis_state == "online")
        except Exception as e:
            print(f"[NewUI] ⚠ 状态更新失败: {e}")

    @staticmethod
    def _active_pet_name() -> str:
        """当前活动桌宠的显示名（拿不到就返回空串，界面照常显示）"""
        try:
            from pets.pet_registry import get_active_pet_id, get_pet_config
            cfg = get_pet_config(get_active_pet_id()) or {}
            return str(cfg.get("display_name") or cfg.get("name") or "").strip()
        except Exception:
            return ""

    # ── 启动/关闭 ──
    # ── 启动/关闭：进行中按钮置灰 + 文案，防止连点 ──

    def _busy_btn(self, btn, text: str, ms: int = 6000):
        try:
            btn.setEnabled(False)
            btn.setText("  " + text)
            QTimer.singleShot(ms, lambda: (btn.setEnabled(True), self.refresh_status()))
        except Exception:
            pass

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
            self._busy_btn(self.btn_pet, "正在关闭中…", 8000)
            self.status_lbl.setText("正在关闭桌宠…")
            QTimer.singleShot(9000, lambda: self.status_lbl.setText(""))
            print("[NewUI] 正在关闭桌宠…")
            _send_control("shutdown")
            # 轮询等它真的退出（最多 12 秒），再刷新状态
            self._wait_pet_gone(12)
            return
        self._busy_btn(self.btn_pet, "正在启动中…", 15000)
        if self._launch_pet():
            # 用 0.5 秒轮询等它起来（以前固定等 6 秒，起来了也要干等）
            self._poll_pet_up()

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

    # ── 换角色（用户："每次设置活动，可以立即切换桌宠，0.5 秒，而不是等 6 秒"）──

    def schedule_pet_switch(self, pet_name: str = "", delay_ms: int = 500):
        """「设为活动」后延迟 delay_ms 再真正切桌宠。

        延迟是**防误触**：连点几个角色时只有最后那个生效（0.5 秒内重复调用会重置计时）。
        反馈立刻给（芯片/状态行），不让用户干等。
        """
        self._switch_name = pet_name or self._active_pet_name() or "活动角色"
        if getattr(self, "_switch_timer", None) is None:
            self._switch_timer = QTimer(self)
            self._switch_timer.setSingleShot(True)
            self._switch_timer.timeout.connect(self._do_pet_switch)
        self._switch_timer.start(max(0, int(delay_ms)))
        try:
            self.chip_pet.set_text(f"桌宠（{self._switch_name}）：正在切换…", False)
            self.status_lbl.setText(f"正在切换成「{self._switch_name}」…")
        except Exception:
            pass
        print(f"[NewUI] 已排队换角色 → {self._switch_name}（{delay_ms}ms 防误触）")

    def _do_pet_switch(self):
        """真正切：桌宠在跑 → 关掉它、并用**新活动角色**重新起来；没在跑 → 只提示去哪启动。

        以前这里只写注册表 + 弹一句"关掉再启动就会换成它"，用户得自己开关一次，
        且启动后用固定 6 秒才刷状态。现在启动器自己完成这次切换，并用 0.5 秒轮询
        等它回来（起来了立刻刷新状态）。
        """
        name = getattr(self, "_switch_name", "") or self._active_pet_name()
        if not _pet_api_alive():
            try:
                self.status_lbl.setText(f"已设为「{name}」｜回总览点「启动 AIpet 桌宠」即可")
                QTimer.singleShot(6000, lambda: self.status_lbl.setText(""))
            except Exception:
                pass
            self.refresh_status()
            return
        try:
            self._busy_btn(self.btn_pet, "正在切换角色…", 30000)
            self.status_lbl.setText(f"正在把桌宠换成「{name}」…")
        except Exception:
            pass
        print(f"[NewUI] 换角色：先关掉当前桌宠（{name}）")
        _send_control("shutdown")

        def _work():
            import time as _t
            for _ in range(60):                 # 最多 30 秒等它退出
                _t.sleep(0.5)
                if not _pet_api_alive():
                    break
            self._launch_pet()                  # 用新活动角色重新启动
            for _ in range(60):                 # 最多 30 秒等它回来
                _t.sleep(0.5)
                if _pet_api_alive():
                    break
            try:
                self._switch_done.emit(name)    # 回 UI 线程收尾（按钮/状态/芯片）
            except Exception:
                pass

        import threading
        threading.Thread(target=_work, daemon=True).start()

    def _on_switch_done(self, name: str):
        """换角色收尾（UI 线程）：按钮恢复 + 立刻刷新状态，不再等 6 秒"""
        try:
            self.btn_pet.setEnabled(True)
            self.status_lbl.setText(f"桌宠已换成「{name}」")
            QTimer.singleShot(4000, lambda: self.status_lbl.setText(""))
        except Exception:
            pass
        self.refresh_status()
        print(f"[NewUI] 换角色完成 → {name}")

    def _require_python(self, what: str, need=()) -> str:
        """启动桌宠/QQ/微信前先确认有可用解释器；没有就说清**为什么**、**怎么修**。

        ⚠ 三个入口原来各写一份 `py = _find_python(base)`，微信那处还把"没有解释器"和
          "缺 run_wechat.py"混在同一个 if 里 → 包内明明有 run_wechat.py，却报
          "未找到微信模块（run_wechat.py）"，把人指向完全错误的方向（用户实测反馈）。
          现在统一成一处，并把"系统 Python 找到了但缺依赖"这种最常见情况单独说清。
        """
        base = _app_base_dir()
        need = tuple(need)
        py = _find_python(base, need)
        if py:
            return py
        mods = "、".join(need)
        sys_py = shutil.which("python") or shutil.which("python3")
        if sys_py:
            why = (f"系统里找到 Python（{sys_py}），但它**缺少运行依赖**"
                   + (f"（需要：{mods}）" if mods else "") + "，所以没有被采用。")
        else:
            why = ("系统里也没找到 Python（PATH 上没有 python）。"
                   + (f"{what}需要这些模块：{mods}。" if mods else ""))
        fix = ("修法：在程序目录里双击一次 install.bat —— 它会建好 runtime\\venv 并装齐依赖，"
               "装完再点这个按钮。\n（或按 README 装好 Python 3.10，安装时勾上 "
               "\"Add Python to PATH\"，再重跑 install.bat。）"
               if getattr(sys, "frozen", False) else
               "修法：按 README 跑一次 install.bat（建 runtime\\venv 并装依赖）；"
               "或者用一个装好依赖的 Python 运行 run_launcher.py。")
        self._msg(f"{what}起不来", f"没有可用的运行环境（缺 {mods or '依赖'}）。",
                  f"{why}\n\n{fix}")
        return ""

    def _launch_pet(self):
        """启动桌宠进程（toggle_pet 与换角色共用）"""
        base = _app_base_dir()
        py = self._require_python("桌宠", PET_NEED)
        if not py:
            return False
        # 本地视觉模型（屏幕/摄像头识别）跟着桌宠一起起：加载要几秒，先开好再启动桌宠
        try:
            ensure_vision_service(self.shell)
        except Exception as e:
            print(f"[NewUI]  启动本地视觉服务失败（不影响桌宠）: {e}")
        try:
            self.shell._pet_proc = subprocess.Popen([py, os.path.join(base, "run.py")], cwd=base,
                                                    creationflags=_spawn_flags())
            print("[NewUI] 已启动桌宠（run.py）")
            return True
        except Exception as e:
            try:
                self._msg("启动失败", "桌宠没能启动。", str(e))
            except Exception:
                pass
            return False

    def _poll_pet_up(self, tries: int = 60):
        """启动后用 0.5 秒轮询代替「固定等 6 秒」：桌宠一回来就刷新状态/按钮"""
        def _work():
            import time as _t
            for _ in range(int(tries)):
                _t.sleep(0.5)
                if _pet_api_alive():
                    break
            try:
                self._switch_done.emit(self._active_pet_name() or "")
            except Exception:
                pass
        import threading
        threading.Thread(target=_work, daemon=True).start()

    def reset_pet_pos(self):
        """把桌宠移回屏幕中央（找不到桌宠时用）"""
        if not _pet_api_alive():
            self._msg("重置桌宠位置", "桌宠还没启动哦，先点「启动 AIpet 桌宠」。")
            return
        self._busy_btn(self.btn_reset_pos, "正在移动…", 4000)
        _send_control("reset_position")
        self.status_lbl.setText("让桌宠回到屏幕中央…")
        QTimer.singleShot(4500, lambda: self.status_lbl.setText(""))
        print("[NewUI] 已发送「重置桌宠位置」")

    def start_qq(self):
        """启动 QQ AIpet：**先确保 NapCat 在跑**，再起 QQ 桥接。

        用户要求的行为（原来缺的就是这一步）：以前这个按钮只跑 run_qq.py，NapCat 得自己
        先启动（`启动QQ.bat` 里那句话就是"请确保 NapCat 已启动"）。而 run_qq.py 本身会等
        （3001 未监听就自动重试），所以卡人的从来不是顺序，是**没人替你拉 NapCat**。
        """
        if self.shell._qq_proc is not None and self.shell._qq_proc.poll() is None:
            self.shell._qq_proc = None      # 已经退出/异常 → 允许重启
        self._busy_btn(self.btn_qq, "正在检查 NapCat…", 120000)
        self._ensure_napcat("start_qq")

    def start_wechat(self):
        base = _app_base_dir()
        py = self._require_python("微信 AIpet", WX_NEED)
        if not py:
            return
        # 解释器有了，再单独查"文件在不在"（两件事分开报，别混成一句误导话）
        if not os.path.exists(os.path.join(base, "run_wechat.py")):
            self._msg("微信 AIpet", "未找到微信模块（run_wechat.py）。",
                      "微信桥接随程序包一起提供；如果你是精简安装，请把 wechat 目录补回来。")
            return
        # ⚠ 微信通道没开时**别去拉进程**：run_wechat.py 会在第一行打印
        #   "wechat_enabled=false，微信桌宠未启用" 然后立刻退出 → 控制台一闪就没，
        #   用户会以为"崩溃了"（实测反馈）。这里改成主题提示，并说清去哪儿开。
        try:
            from tool.config import as_bool as _as_bool, get_config as _get_cfg
            if not _as_bool(_get_cfg(os.path.join(base, "config.json")).get("wechat_enabled"), False):
                self._msg("微信 AIpet", "微信通道还没启用。",
                          "去「设置 → 微信」打开「启用微信 ClawBot（iLink）」再点这个按钮。\n"
                          f"（当前 config.json 里 wechat_enabled = false：{os.path.join(base, 'config.json')}）")
                return
        except Exception as e:
            print(f"[NewUI] ⚠ 读取微信开关失败（继续尝试启动）: {e}")
        self._busy_btn(self.btn_wx, "正在启动微信…", 12000)
        try:
            self.shell._wx_proc = subprocess.Popen([py, os.path.join(base, "run_wechat.py")], cwd=base,
                                                   creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            self._msg("启动失败", "微信桥接没能启动。", str(e))

    # ── 工具 ──

    def open_studio(self):
        try:
            from .portrait_studio import PortraitStudio
            # 挂在外壳上：换肤重建总览页后仍是同一个工坊实例
            self._studio = getattr(self.shell, "_portrait_studio", None) or PortraitStudio(self.window())
            self.shell._portrait_studio = self._studio
            self._studio.show(); self._studio.raise_(); self._studio.activateWindow()
        except Exception as e:
            self._msg("立绘工坊", "打开失败。", str(e))

    def open_pet_settings(self):
        try:
            from .pet_wizard import PCLPetWizard
            from pets.pet_registry import get_active_pet_id
            dlg = PCLPetWizard(get_active_pet_id(), self.window())
            dlg.show(); dlg.raise_(); dlg.activateWindow()   # 非模态，避免锁住预览窗口
        except Exception as e:
            self._msg("桌宠设置", "打开失败。", str(e))

    def open_napcat_webui(self):
        """打开 NapCat WebUI。**没在跑就先把它拉起来**，而不是弹一个打不开的对话框。

        用户要求：点这个按钮应该拉起 NapCat。所以现在是
        「探端口 → 没跑就 launcher-user.bat 拉起来并等待 → 就绪后直接打开带 token 的面板」；
        只有真的拉不起来（缺脚本/超时）才提示，而且提示是主题一致的消息框（正文高对比、
        路径可复制、不用 emoji —— QMessageBox 里的 emoji 在部分机器上会渲染成方块）。

        端口/token 仍从 NapCat 自己的 webui.json 读（config.json 里没有 WebUI token）。
        """
        self._busy_btn(getattr(self, "btn_webui", self.btn_reset_pos),
                       "正在启动 NapCat…", 120000)
        self._ensure_napcat("open_webui")

    def napcat_relogin(self):
        """强制拉起 NapCat 重新扫码（跟「启动 QQ」用的是同一条脚本）。"""
        bat = _napcat_launcher_bat()
        if os.path.exists(bat):
            try:
                subprocess.Popen([bat], cwd=os.path.dirname(bat),
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
                self._msg("重新扫码登录",
                          "已打开 NapCat 登录窗口，请用手机 QQ 扫描窗口里的二维码。",
                          "二维码也保存在：" + os.path.join(
                              _app_base_dir(), "NapCat.Shell.Windows.OneKey", "NapCat",
                              "cache", "qrcode.png"))
            except Exception as e:
                self._msg("重新登录", "拉起 NapCat 失败。", str(e))
        else:
            self._msg("重新登录", "没找到 NapCat 的启动脚本。", bat)

    def open_app_dir(self):
        try:
            os.startfile(_app_base_dir())    # noqa
        except Exception as e:
            print(f"[NewUI] 打开目录失败: {e}")
            # 用户点了「打开程序目录」却什么都没发生 → 说清楚（以前只写控制台）
            self._msg("打开程序目录", "没能打开资源管理器。", f"{e}\n目录：{_app_base_dir()}")

    def open_changelog(self):
        """首页快捷入口「📜 更新日志」：用**主题化阅读窗口**打开（可切版本）。

        ⚠ 以前这里是 `sorted(glob(...), reverse=True)[0]` + `os.startfile`：
          ① 按文件名字典序取"最新" → `V1.8.0.md` 会排在 `V1.16.1.md` 前面，点开的是旧版本；
          ② 把 .md 甩给系统默认程序，没装 markdown 阅读器时只会弹「打开方式」；
          ③ 目录为空只会说「未找到更新日志文件」。
        现在统一走 `pcl_launcher.changelog`（按版本号排序 + 主题窗口 + 目录空时回退读 README）。
        """
        try:
            from . import changelog as _cl
            _cl.show(self)
        except Exception as e:
            self._msg("更新日志", "打开失败。", str(e))

    def _do_start_qq(self):
        base = _app_base_dir()
        py = self._require_python("QQ AIpet", QQ_NEED)
        if not py:
            return
        if not os.path.exists(os.path.join(base, "run_qq.py")):
            self._msg("QQ AIpet", "未找到 QQ 模块（run_qq.py）。",
                      "QQ 桥接随程序包一起提供；如果你是精简安装，请把 qq 目录补回来。")
            return
        self._busy_btn(self.btn_qq, "正在启动 QQ…", 12000)
        try:
            self.shell._qq_proc = subprocess.Popen([py, os.path.join(base, "run_qq.py")], cwd=base,
                                                   creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.status_lbl.setText("QQ AIpet 已启动；未登录时会在 NapCat 窗口里显示二维码。")
            QTimer.singleShot(12000, self.refresh_status)
        except Exception as e:
            self._msg("启动失败", "QQ AIpet 没能启动。", str(e))
            self.refresh_status()

    # ── 确保 NapCat 在跑（拉起 + 等待就绪）──

    def _do_open_webui(self):
        try:
            from qq.qq_config import discover_webui_url
            info = discover_webui_url()
        except Exception as e:
            info = {"url": "http://127.0.0.1:6099/webui", "port": 6099, "token": "", "source": str(e)}
        port = int(info.get("port") or 6099)
        if not _local_port_open(port):
            # 起来了但面板端口还没监听（多半还在等扫码）→ 说清现状与下一步
            self._msg("NapCat WebUI 还没就绪",
                      "NapCat 已经在运行，但 WebUI 端口 %d 还没开始监听（通常是因为还没扫码登录）。"
                      % port,
                      "请在弹出的 NapCat 窗口里用手机 QQ 扫码登录，登录成功后再点一次这个按钮。\n"
                      "二维码文件：" + os.path.join(
                          _app_base_dir(), "NapCat.Shell.Windows.OneKey", "NapCat",
                          "cache", "qrcode.png"))
            print(f"[NewUI] NapCat WebUI 未打开：{port} 端口无监听")
            return
        import webbrowser
        webbrowser.open(info["url"])
        print("[NewUI] 已打开 NapCat WebUI：端口 %d，token %s（来源：%s）"
              % (port, "已带" if info.get("token") else "无", info.get("source")))

    def _ensure_napcat(self, action: str, timeout_s: int = None):
        """没跑就把 NapCat 拉起来（可见控制台：二维码在那个窗口里），并等待它**这次要用的**端口就绪。

        就绪判据按用途分（这点很关键）：
          · 启动 QQ  → 看 WS 端口（默认 3001，QQ 桥接要连它）
          · 打开 WebUI → 看 WebUI 端口（默认 6099，面板要它）
        拉起后**只等这一件事**，不要拿另一个端口当门槛（否则"面板明明能开却报没就绪"）。
        NapCat 在扫码期间 WS 可能还没监听 → 我们照实说明"已在等待扫码"，不装作已就绪。
        """
        if getattr(self, "_napcat_busy", False):
            return
        self._napcat_busy = True
        wait_s = int(NAPCAT_WAIT_S if timeout_s is None else timeout_s)
        ws_port = _napcat_ws_port()
        webui_port = 6099
        try:
            from qq.qq_config import discover_webui_url
            webui_port = int(discover_webui_url().get("port") or 6099)
        except Exception:
            pass
        need_port = webui_port if action == "open_webui" else ws_port
        bat = _napcat_launcher_bat()
        self._napcat_progress.emit("正在检查 NapCat…")

        def _work():
            try:
                if _local_port_open(need_port):
                    self._napcat_done.emit(True, "NapCat 已在运行。", action)
                    return
                if not os.path.isfile(bat):
                    self._napcat_done.emit(
                        False, "没找到 NapCat 的启动脚本，" + os.path.basename(bat) + " 不在包里。",
                        action)
                    return
                try:
                    subprocess.Popen([bat], cwd=os.path.dirname(bat),
                                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
                except Exception as e:
                    self._napcat_done.emit(False, "拉起 NapCat 失败：" + str(e), action)
                    return
                self._napcat_progress.emit(
                    "已拉起 NapCat，等待它启动……（首次使用请在弹出的窗口里用手机 QQ 扫码）")
                deadline = time.time() + max(2, wait_s)
                said_scan, said_login = False, False
                while time.time() < deadline:
                    time.sleep(1.5)
                    if _local_port_open(need_port):
                        self._napcat_done.emit(True, "NapCat 已就绪。", action)
                        return
                    if not said_scan and _local_port_open(webui_port):
                        said_scan = True
                        self._napcat_progress.emit(
                            "NapCat 已启动，正在等待扫码登录……（二维码在 NapCat 窗口里，"
                            "也保存在 NapCat.Shell.Windows.OneKey\\NapCat\\cache\\qrcode.png）")
                    elif not said_login and _local_port_open(ws_port):
                        said_login = True
                        self._napcat_progress.emit("NapCat 已登录，正在等它把面板端口就绪…")
                # 超时：可能还在扫码，也可能 QQ 路径不对（launcher-user.bat 会打印 invalid 后暂停）
                self._napcat_done.emit(
                    False,
                    "NapCat 启动了但还没就绪（多半是在等扫码）。" if said_scan
                    else "NapCat 启动了但端口一直没监听。", action)
            except Exception as e:
                self._napcat_done.emit(False, "处理 NapCat 时出错：" + str(e), action)

        threading.Thread(target=_work, daemon=True).start()

    def _on_napcat_done(self, ready: bool, msg: str, action: str):
        self._napcat_busy = False
        self.status_lbl.setText(msg)
        if action == "open_webui":
            if ready:
                self._do_open_webui()
            else:
                self._napcat_failed_dialog(msg)
            return
        if action == "start_qq":
            # NapCat 没就绪也照样起 QQ 桥接：它会自己等 3001（设计如此），
            # 而且用户在扫码期间就能看到 QQ 窗口，不必再点第二次。
            self._do_start_qq()
            if not ready:
                self.status_lbl.setText(msg + " QQ AIpet 已同时启动，它会自动等 NapCat 就绪。")
            QTimer.singleShot(15000, self.refresh_status)

    def _napcat_failed_dialog(self, why: str):
        """NapCat 拉不起来时的提示：主题一致的消息框、正文高对比、路径可选中复制。"""
        from .silicon_dialog import message as _msg
        _msg(self.window(), "NapCat 没能就绪", why,
             "可以手动启动它：\n"
             + _napcat_launcher_bat() + "\n"
             "启动后窗口里会有二维码，用手机 QQ 扫码登录；"
             "登录成功后 WS 端口（默认 3001）才会监听，WebUI 也才能打开。\n"
             "如果这个脚本报 \"provided QQ path is invalid\"，说明注册表里没有 QQ，"
             "改用随包的 NapCat.Shell.Windows.OneKey\\start_napcat.bat。")

    def _msg(self, title: str, text: str, detail: str = ""):
        """统一用主题一致的消息框（见 silicon_dialog.MessageDialog 的说明）"""
        try:
            from .silicon_dialog import message as _m
            _m(self.window(), title, text, detail)
        except Exception as e:
            print(f"[NewUI] ⚠ 消息框失败: {e}")

# ══════════════════════ 主窗口 ══════════════════════
class SiliconLauncher(QWidget):
    """AIpet 启动器 · 新版外壳"""

    # 视频背景解码线程 → GUI 线程的帧通道
    # （普通线程里 emit 这个信号，Qt 会自动排队到主线程执行槽，别直接碰控件）
    _video_frame_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        _ensure_src_on_path()        # 冻结版：页面懒加载用得到随包源码
        self._pet_proc = None
        self._qq_proc = None
        self._wx_proc = None
        self._bg_widget = None
        self._media = None
        self._bg_reader = None        # 主题视频背景：OpenCV 解码线程（见 _VideoBgReader）
        self._bg_video_frame = None   # 最新一帧（Live2D 预览区同步取用）
        self._bg_video_serial = 0
        self._bg_frame_busy = False
        self._video_frame_signal.connect(self._on_bg_video_frame)

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
                                ("✕", self.close, "关闭")):
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
            QPushButton:hover {{ background: {'#e03030' if text == '✕' else SF(0.16)};
                color: {'white' if text == '✕' else Color1.name()}; }}
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
            self.nav_btns[key] = b
            lay.addWidget(b)
        lay.addStretch()

        # ── 左下角：设置入口（按需求放在左下角）+ 版本信息 ──
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {Color5.name()}; border: none;")
        lay.addWidget(sep)
        b_set = NavRailButton("", "设置", "模型 · 语音 · 外观", icon_key="settings")
        b_set.clicked.connect(lambda _=False: self._goto("settings"))
        self.nav_btns["settings"] = b_set
        lay.addWidget(b_set)
        # 版本戳：把这份 silicon_window.py 的修改时间显示出来 ——
        # 排查"我换了新 exe 怎么没变化"时，页面右下角这行就能证明跑的是哪一版
        try:
            import time as _tmv
            _stamp = _tmv.strftime("%m-%d %H:%M", _tmv.localtime(os.path.getmtime(__file__)))
        except Exception:
            _stamp = "?"
        ver = QLabel("Silicon UI · 新版 · " + _stamp)
        # ⚠ 以前用 Gray3：浅色主题下这条页脚压在侧栏的浅色面上只有 1.6:1（实测），
        #   基本看不见；换成主题的次级文字色（浅色主题 5.2:1 / 深色主题 9.9:1）。
        ver.setStyleSheet(f"color: {Gray2.name()}; font-size: 11px; padding: 2px 8px;")
        ver.setToolTip("这是当前启动器代码的时间戳（排查旧进程用）：%s\n程序目录：%s"
                       % (_stamp, _app_base_dir()))
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
                _make_transparent(w, alpha=_page_block_alpha())
            except Exception as _e:
                print(f"[NewUI] ⚠ 页面透明化失败({key}): {_e}")
            # ⚠ 页面会自我刷新（点「设置」→ 桌宠列表 _refresh() / 插件页 _reload()），
            #   重建出来的卡片带回内联实心背景色 → 又挡住主题壁纸（表现为「点设置后背景被遮挡」）。
            #   这里挂钩刷新方法：重建后自动再透明化一次。
            try:
                _hook_repaint_transparency(w)
            except Exception as _e:
                print(f"[NewUI] ⚠ 透明化挂钩失败({key}): {_e}")
            self.pages[key] = w
            self.stack.addWidget(w)
            if key == "home":
                self.home = w
            self._wire_page_theme(w)
            return w
        except Exception as e:
            import traceback
            print(f"[NewUI] ⚠ 页面 {key} 加载失败: {e}\n{traceback.format_exc()[:400]}")
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
            # 记忆页的「🔄 重新扫码登录微信」按钮：这个信号以前**没人接**，
            # 点了完全没反应（用户报"重新登录微信桌宠好像坏了"）。
            sig3 = getattr(page, "wechat_relogin_requested", None)
            if sig3 is not None and not getattr(page, "_wx_relogin_wired", False):
                sig3.connect(self.wechat_relogin)
                page._wx_relogin_wired = True
        except Exception as e:
            print(f"[NewUI] ⚠ 主题信号挂接失败: {e}")

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
                    f"color: {Gray2.name()}; font-size: 11px; padding: 2px 8px;")
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
            # 背景重载**不在这里**做：它必须无条件执行（见 apply_theme_live 里的调用），
            # 放在这个 try 里一旦前面某步抛异常就会被跳过 → 旧主题的视频还会继续播。
        except Exception as e:
            print(f"[NewUI] ⚠ 外壳重设样式失败: {e}")

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

        ⚠ 快照是「一张不透明的旧页面位图」叠在内容区上：只要它没被删掉，
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
            print(f"[NewUI] ⚠ 快照淡出失败（直接删除）: {e}")
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
                    print(f"[NewUI] ⚠ 主题写入 config 失败: {e}")
            from . import colors as _C
            _C.apply_theme_live(theme_id)
            _reset_style_caches()          # 壁纸有无变了 → SF() 的不透明度跟着变
            self._accent = _C.accent_hex()
            # 全局 QSS + 调色板（主题底色不同 → 文字深浅跟着变）
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is not None:
                    silicon_ui.install(app, accent=self._accent)
            except Exception as e:
                print(f"[NewUI] ⚠ 全局样式重建失败: {e}")
            self._silicon = theme_id == "silicon"
            cur_key = self._current_page_key()
            self._restyle_chrome()
            # 换肤后**必须**重载背景（放在这里、且单独 try —— 不能被外壳样式那段的异常跳过）：
            # 主题可能是"视频 → 无背景/图片"，不重载就会留着旧主题的视频线程继续播，
            # 而新主题的遮罩色又会被套到旧画面上 → 用户看到的"切了主题背景没变，只多一层蒙版"。
            try:
                self.reload_background()
            except Exception as e:
                print(f"[NewUI] ⚠ 换肤后重载背景失败: {e}")
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
            print(f"[NewUI] ⚠ 实时应用主题失败: {e}")
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
            print(f"[NewUI] ⚠ 实时应用强调色失败: {e}")

    def wechat_relogin(self):
        """记忆页的「🔄 重新扫码登录」：停掉微信桥接 → 清本地凭据 → 重新启动出码。

        ⚠ 以前记忆页那个按钮只 `emit()` 了 `wechat_relogin_requested`，**外壳没人接**
          → 点了完全没反应（用户报"记忆页里面的重新登录微信桌宠好像坏了"）。
        """
        from .silicon_dialog import page_confirm, page_msg
        ok = True
        try:
            ok = page_confirm(
                self, "重新扫码登录微信",
                "会先关掉正在运行的微信桥接，并清除本机保存的登录凭据，然后重新出码扫码。",
                "换绑 / 换手机 / 登录异常时用。聊天记录与角色记忆不受影响（只清登录凭据）。",
                ok_text="清除并重新扫码", danger=True)
        except Exception as e:
            print(f"[NewUI] ⚠ 重新登录确认框打开失败，直接执行: {e}")
        if not ok:
            return

        # 1) 停掉正在跑的微信桥接（进程句柄在外壳上）
        stopped = False
        proc = getattr(self, "_wx_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                for _ in range(12):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.25)
                if proc.poll() is None:
                    proc.kill()
                stopped = True
            except Exception as e:
                print(f"[NewUI] ⚠ 关闭微信桥接失败: {e}")
        self._wx_proc = None

        # 2) 清掉本地登录凭据（只清凭据，聊天记录/记忆不动）
        removed = []
        try:
            from wechat.ilink_client import CRED_FILE
            if os.path.exists(CRED_FILE):
                os.remove(CRED_FILE)
                removed.append(os.path.basename(CRED_FILE))
        except Exception as e:
            print(f"[NewUI] ⚠ 清除微信登录凭据失败: {e}")

        # 3) 重新启动（新控制台里会打印二维码）
        home = self.pages.get("home")
        started = False
        try:
            if home is not None and hasattr(home, "start_wechat"):
                home.start_wechat()
                started = True
        except Exception as e:
            print(f"[NewUI] ⚠ 重新启动微信桥接失败: {e}")

        try:
            page_msg(self, "重新扫码登录微信",
                     "已清掉本地登录凭据，微信桥接正在重新启动。",
                     ("新开的那两个控制台里会显示二维码，用手机微信扫一下即可"
                      if started else "请在「总览」点「启动微信 AIpet」重新出码") +
                     "\n\n本次清理：" + ("、".join(removed) if removed else "没有凭据文件（本来就没登录过）") +
                     ("\n已关闭旧的微信桥接进程" if stopped else ""))
        except Exception as e:
            print(f"[NewUI] ⚠ 重新登录结果提示失败: {e}")
        print(f"[NewUI] 微信重新登录：清理 {removed or '无'}，"
              f"桥接{'已关闭' if stopped else '本来没在跑'}，{'已重新启动' if started else '未能自动启动'}")

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
            # ⚠ 硬兜底：动画被打断/特效对象提前释放时，快照也必须消失
            #   （否则那张不透明的旧页面位图会一直盖在新页面上 = 「背景被遮挡」）
            QTimer.singleShot(470, lambda: self._drop_snap(snap))
            self._page_anim = (a1, a2)
        except Exception:
            self.stack.setCurrentWidget(w)
        try:
            # 切到该页时再兜一次（页面可能刚被刷新/重建过）
            _make_transparent(w, alpha=_page_block_alpha())
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
    def _apply_effects(self):
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
                    print(f"[NewUI] ⚠ 圆角设置失败: {_e}")
                print("[NewUI] 亚克力已关闭（保留圆角，更流畅）")
                return
        except Exception:
            pass
        try:
            silicon_ui.apply_acrylic(self)
            print("[NewUI] 亚克力 + 圆角已启用")
        except Exception as e:
            print(f"[NewUI] ⚠ 亚克力失败: {e}")

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
            print(f"[NewUI] ⚠ 模糊刷新调度失败: {e}")

    def _finish_blur_refresh(self):
        self._bg_blur_skip = False
        self.reload_background()

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
            # ── 改「启动器底色」→ 走与「切主题」同一条**全套换肤**路径 ────────────
            # ⚠ 以前这里只刷新了背景画面 + 二级窗口：色板（Color1/Color6/Color8…）没重算、
            #   全局 QSS 没重装、页面没重建 → 卡片、文字、输入框全都不跟着变，
            #   非得重启启动器才生效（用户反馈"文字颜色和卡片 ui 还是没跟随背景底色"）。
            if "ui_bg_color" in (values or {}):
                try:
                    from .colors import current_theme_id as _ctid_bg, base_bg_color as _bbc_bg
                    self._bg_blur_skip = True
                    try:                                   # 外壳自己那块底板也立刻换
                        self._set_base_color(_bbc_bg())
                    except Exception as _e0:
                        print(f"[NewUI] ⚠ 外壳底板换色失败: {_e0}")
                    self.apply_theme_live(_ctid_bg(), persist=False)   # 重算色板+重装 QSS+重建当前页
                    self._schedule_blur_refresh(400)
                    print("[NewUI] 启动器底色已实时生效（卡片 / 文字 / 二级窗口一起换）")
                    return
                except Exception as _e_bg:
                    print(f"[NewUI] ⚠ 底色全套换肤失败（退回只刷背景）: {_e_bg}")
            # 二级窗口（立绘工坊/新建桌宠…）实时跟随启动器底色
            try:
                if "ui_bg_color" in (values or {}):
                    from .silicon_dialog import refresh_all_dialog_colors
                    refresh_all_dialog_colors(values.get("ui_bg_color"))
            except Exception as _e:
                print(f"[NewUI] ⚠ 同步二级窗口底色失败: {_e}")
            self._bg_blur_skip = True      # 拖动中：先不做模糊（毫秒级响应）
            self.reload_background()
            self._schedule_blur_refresh(400)   # 停手后补上模糊
        except Exception as e:
            print(f"[NewUI] ⚠ 实时应用背景设置失败: {e}")

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

    def _load_background(self):
        """主题背景（图片/视频）：铺满整窗，内容叠在上面"""
        try:
            # 背景底色：壁纸半透明时透出来的那层
            # （用户自选了「启动器底色」就用它；没选 = 跟随主题 → 保留主题自己的
            #   底板色，经典/樱华是浅色主题，硬套黑色会让深色文字看不见）
            try:
                _bc = str(self._bg_value("ui_bg_color", "") or "").strip()
                if _bc:
                    self._set_base_color(QColor(_bc))
            except Exception:
                pass
            btype, src, opacity = background_info()
            # 用户在主题页可调：背景透明度 / 模糊度 / 遮罩强度
            try:
                _o = self._bg_value("ui_bg_opacity", 100)
                if _o not in (None, ""):
                    opacity = max(0.05, min(1.0, float(_o) / 100.0))
                self._bg_blur = int(self._bg_value("ui_bg_blur", 0) or 0)
            except Exception:
                self._bg_blur = 0
            # 背景遮罩：把画面朝主题底色混一层，保证上层文字可读
            # （樱华主题是角色拼贴背景，不遮的话文字完全糊住 = 用户报的"看不清字"）
            try:
                _sc = self._bg_value("ui_bg_scrim", None)
                self._bg_scrim = 0.55 if _sc in (None, "") else max(0.0, min(0.95, float(_sc) / 100.0))
            except Exception:
                self._bg_scrim = 0.55
            if not src:
                # 新主题没有背景声明 → **显式清空底板**。
                # 以前这里是直接 return：底板还留着上一个主题的视频最后一帧，
                # 看起来就像"背景没变"（用户报的现象之一）。
                try:
                    self.back.set_bg(QPixmap())
                    self.back.update()
                except Exception:
                    pass
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
                pm = self._apply_scrim(pm)
                try:
                    self.back.set_bg(pm)
                    self.back.lower()          # 底板在最底层（内容叠在上面）
                    self.back.update()
                except Exception as _e:
                    print(f"[NewUI] ⚠ 设置圆角壁纸失败: {_e}")
            elif btype == "video":
                self._start_video_background(src, opacity)
        except Exception as e:
            print(f"[NewUI] ⚠ 主题背景加载失败: {e}")

    def _apply_scrim(self, pm):
        """在背景画面（图片或视频帧）上叠一层主题底色的半透明遮罩。

        为什么需要：主题背景是整窗铺满的，而面板本身是半透明的
        （Color8 带 alpha 215）→ 背景一花，上层文字就糊在画面里看不出来。
        樱华主题的 assets/bg.jpg 是角色拼贴画，用户报的「看不清字」正是这个。
        遮罩把画面朝主题底色混一层：浅色主题偏奶白、深色主题偏深，文字立刻可读。
        默认 55%（主题页可调，0% = 原始画面）。
        """
        try:
            k = float(getattr(self, "_bg_scrim", 0.55) or 0.0)
            if k <= 0.001 or pm is None or pm.isNull():
                return pm
            out = QPixmap(pm.size())
            out.fill(Qt.transparent)
            p = QPainter(out)
            p.drawPixmap(0, 0, pm)
            c = QColor(Color8)                  # 主题底色（浅主题奶白 / 深主题深灰）
            c.setAlphaF(min(0.95, k))
            p.fillRect(out.rect(), c)
            p.end()
            return out
        except Exception as e:
            print(f"[NewUI] ⚠ 背景遮罩失败: {e}")
            return pm

    def _start_video_background(self, src, opacity):
        """主题视频背景：OpenCV 解码线程 → 逐帧刷到**已有的圆角底板**（不用 QtMultimedia）。

        为什么不用 QMediaPlayer/QVideoWidget（原来就是这么写的，用户报"视频根本不播"）：
          1) 本机实测 Qt5.15 的 WMF/DirectShow 打不开 H.264 mp4 ——
             `DirectShowPlayerService::doRender: Unknown error 0x80040266`
             → mediaStatus=InvalidMedia、duration=0；而 cv2(ffmpeg) 正常解出
             1900 帧/30fps（证据：_audit_fish9269/probe_video_decode.py，实测）。
          2) 原来那段还调了 `self._apply_bg_mask()`——**全仓库没有这个函数**，
             抛 AttributeError 被 except 吞掉 → 后面的 setGeometry 永不执行 →
             QVideoWidget 停在默认 100×30，所以"看不出哪里该播"。
          3) QVideoWidget 是原生子窗口：圆角/亚克力/透明度都套不上，还会盖住内容页。
        现在复用图片壁纸那条路（self.back.set_bg）：圆角、透明度、层级全部一致。
        """
        try:
            self._stop_video_background()
            self._bg_video_opacity = float(opacity or 1.0)
            self._bg_reader = _VideoBgReader(src, self._video_frame_signal.emit)
            # 解码线程按窗口大小先缩好再送（cover 裁切），GUI 线程只负责贴图
            self._bg_reader.set_target(self.back.width(), self.back.height())
            self._bg_reader.start()
            print(f"[NewUI] 主题背景视频（OpenCV 解码）: {os.path.basename(src)}")
        except Exception as e:
            print(f"[NewUI] ⚠ 视频背景不可用（已跳过）: {e}")
            self._bg_reader = None

    def _stop_video_background(self):
        r = self._bg_reader
        self._bg_reader = None
        if r is not None:
            try:
                r.stop()
            except Exception:
                pass

    def _on_bg_video_frame(self, img):
        """解码线程送来一帧 → 按透明度处理 → 贴到圆角底板。

        · 用 _bg_frame_busy 做背压：上一帧还没贴完就丢掉新帧，避免 GUI 线程堆积
        · 模糊（ui_bg_blur）对视频**不生效**：每帧都做盒式模糊在 1200×780 上
          30fps 撑不住（图片是一次性的，视频是每帧），宁可不糊也不要卡
        """
        try:
            if img is None or img.isNull():
                return
            # 已经不在放视频了（换主题/停播）→ 丢掉迟到的那一帧。
            # 兜底：万一停止路径出问题，旧主题的视频也不能画到新主题的背景上。
            if getattr(self, "_bg_reader", None) is None:
                return
            self._bg_video_frame = img           # 供 Live2D 预览区同步为 GL 纹理
            self._bg_video_serial += 1
            if self._bg_frame_busy:
                return
            self._bg_frame_busy = True
            try:
                pm = QPixmap.fromImage(img)
                op = float(getattr(self, "_bg_video_opacity", 1.0) or 1.0)
                if op < 0.99:
                    faded = QPixmap(pm.size())
                    faded.fill(Qt.transparent)
                    p = QPainter(faded)
                    p.setOpacity(max(0.05, min(1.0, op)))
                    p.drawPixmap(0, 0, pm)
                    p.end()
                    pm = faded
                pm = self._apply_scrim(pm)
                self.back.set_bg(pm)
                self.back.lower()
                self.back.update()
            finally:
                self._bg_frame_busy = False
        except Exception as e:
            self._bg_frame_busy = False
            print(f"[NewUI] ⚠ 视频帧绘制失败: {e}")

    def reload_background(self):
        """背景透明度/模糊度实时生效：停掉旧解码线程/旧控件 → 按当前 config 重建"""
        try:
            if self._media is not None:
                try:
                    self._media.stop()
                except Exception:
                    pass
                self._media = None
            self._stop_video_background()
            if self._bg_widget is not None:
                self._bg_widget.hide()
                self._bg_widget.deleteLater()
                self._bg_widget = None
            self._load_background()
            print("[NewUI] 背景已按新设置重新加载")
        except Exception as e:
            print(f"[NewUI] ⚠ 重载背景失败: {e}")

    def resizeEvent(self, event):
        try:
            if self._bg_widget is not None:
                self._bg_widget.setGeometry(0, 0, self.back.width(), self.back.height())
            # 视频：把新尺寸告诉解码线程（它在自己的线程里做 cover 缩放）
            if self._bg_reader is not None:
                self._bg_reader.set_target(self.back.width(), self.back.height())
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
            print(f"[NewUI] ⚠ 设置底色失败: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        if self._silicon and not getattr(self, "_fx_done", False):
            self._fx_done = True
            QTimer.singleShot(50, self._apply_effects)
        # 预热重页面：启动空闲时按顺序构建（插件/桌宠/记忆/设置），
        # 之后点导航就是秒开（以前第一次点插件目录会卡一下 = 现建页面）
        if not getattr(self, "_prewarm_started", False):
            self._prewarm_started = True
            self._prewarm_queue = ["plugins", "pets", "memory", "settings", "prompt", "themes"]
            QTimer.singleShot(1500, self._prewarm_next)

    def _prewarm_next(self):
        """逐个预热页面（每个之间留 250ms，绝不影响使用）"""
        try:
            q = getattr(self, "_prewarm_queue", [])
            if not q:
                print("[NewUI] 页面预热完成")
                return
            key = q.pop(0)
            if key not in self.pages:
                import time as _t
                t0 = _t.time()
                self._ensure_page(key)
                print(f"[NewUI] 预热 {key}: {( _t.time()-t0)*1000:.0f}ms")
            QTimer.singleShot(250, self._prewarm_next)
        except Exception as e:
            print(f"[NewUI] ⚠ 预热失败: {e}")

    # ── 关闭清理 ──
    def closeEvent(self, event):
        try:
            for proc in (self._qq_proc, self._wx_proc):
                if proc and proc.poll() is None:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass
        self.hide()
        self._stop_video_background()      # 视频背景解码线程必须停，否则进程退不掉
        if self._media is not None:
            try:
                self._media.stop()
            except Exception:
                pass
        event.accept()
        print("[NewUI] 启动器已关闭")


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


def _widget_alive(w) -> bool:
    """Qt 对象还活着吗？

    换肤会**重建当前页**（旧页面 deleteLater），而挂钩里用 QTimer 排的"稍后再透明化"
    可能落在那之后 → 再去碰已销毁的 C++ 对象就是
    `RuntimeError: wrapped C/C++ object of type ... has been deleted` 刷屏。
    """
    try:
        w.isHidden()          # 随便碰一下，触发 C++ 侧访问
        return True
    except RuntimeError:
        return False
    except Exception:
        return True


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
                            from PyQt5.QtCore import QTimer   # Qt 可能晚一步重建 → 再补两次
                            def _redo(o=owner):
                                if _widget_alive(o):          # 页面已被重建/销毁就别碰了
                                    # ⚠ 必须和"建页时"用同一个 alpha：建页走的是
                                    #   _page_block_alpha()（有壁纸 0.92 / 没壁纸 0.35），
                                    #   这里用默认 0.35 的话，一点「刷新」整页块面就突然变淡
                                    #   （用户报的"点刷新前后不一样"）。
                                    _make_transparent(o, alpha=_page_block_alpha())
                            _redo()                            # 立即
                            QTimer.singleShot(150, _redo)
                            QTimer.singleShot(450, _redo)
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
                print(f"[NewUI] ⚠ 挂钩 {name} 失败: {e}")


class _VideoBgReader:
    """主题视频背景解码线程（OpenCV/ffmpeg）。

    为什么不用 QtMultimedia：本机实测 Qt5.15 的 WMF/DirectShow 引擎打不开 H.264 mp4
    （`DirectShowPlayerService::doRender: Unknown error 0x80040266` → InvalidMedia、
    duration=0），而 cv2 能稳定解出 30fps/1900 帧。老版本就是这么做的（当时写在这段
    代码的注释里），后来换成 QMediaPlayer 才坏的。

    ⚠ 用**守护线程 + 信号回调**，不用 QThread：
      原来写成 QThread 后，只要窗口没走 closeEvent 就被销毁（比如启动器直接
      sys.exit、或者自动化脚本建完窗口就退），Qt 会打印
      `QThread: Destroyed while thread is still running` 然后**整个进程 fail-fast
      崩溃（0xC0000409）**——实测 smoke_pages 稳定复现。守护线程不会有这个问题：
      它不在 Qt 的对象树里，进程退出时自然结束。
    线程内就做 cover 缩放（缩到窗口尺寸再发），GUI 线程只贴图 —— 否则
    1920×1080 的帧每帧在主线程缩放会明显掉帧。
    """

    def __init__(self, path, emit_frame):
        self._path = path
        self._emit = emit_frame          # 一般是 QObject 的 signal.emit（跨线程会走队列）
        self._running = True
        self._lock = threading.Lock()
        self._tw, self._th = 0, 0        # 目标尺寸（窗口大小，0=不缩）
        self._t = threading.Thread(target=self._run, daemon=True,
                                   name="apet-video-bg")

    def start(self):
        self._t.start()

    def set_target(self, w, h):
        """窗口尺寸变化时告知目标大小（下一次解码生效）"""
        with self._lock:
            self._tw, self._th = int(max(0, w)), int(max(0, h))

    def stop(self):
        self._running = False
        try:
            self._t.join(timeout=2.0)    # 守护线程；等不到也不阻塞退出
        except Exception:
            pass

    def _run(self):
        cap = None
        try:
            import cv2
            cap = cv2.VideoCapture(self._path)
            if not cap.isOpened():
                print(f"[NewUI] ⚠ 视频无法打开: {os.path.basename(self._path)}")
                return
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            # 上限 30fps：启动器背景不需要更高，省 CPU
            fps = max(1.0, min(30.0, float(fps)))
            period = 1.0 / fps
            print(f"[NewUI] 视频背景已开播 fps={fps:.1f}")
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)      # 循环重播
                    continue
                with self._lock:
                    tw, th = self._tw, self._th
                if tw > 1 and th > 1:
                    # cover：先按最大比例缩放，再居中裁切到目标尺寸
                    fh, fw = frame.shape[:2]
                    sc = max(tw / float(fw), th / float(fh))
                    nw, nh = int(fw * sc + 0.5), int(fh * sc + 0.5)
                    frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
                    x0, y0 = (nw - tw) // 2, (nh - th) // 2
                    frame = frame[y0:y0 + th, x0:x0 + tw]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
                if self._running:
                    try:
                        self._emit(img)
                    except (RuntimeError, AttributeError):
                        # 宿主窗口已被销毁：PyQt 抛 RuntimeError（wrapped C/C++ object
                        # deleted）或 AttributeError（不再有这个信号）→ 线程安静退出，
                        # 不要在日志里刷异常（实测：测试里把 launcher 的引用丢了就会出现）。
                        return
                time.sleep(period)           # 普通线程没有 msleep，用 time.sleep
        except Exception as e:
            print(f"[NewUI] ⚠ 视频解码线程异常: {type(e).__name__}: {e}")
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass


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
        print(f"[NewUI] ⚠ 高斯模糊不可用，回退缩放模糊: {e}")
        try:
            f = max(2, int(strength) // 6 + 1)
            small = pm.scaled(max(1, pm.width() // f), max(1, pm.height() // f),
                              Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            return small.scaled(pm.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        except Exception:
            return pm


def _local_port_open(port: int, timeout: float = 0.4) -> bool:
    """本机端口有人在监听吗（NapCat WebUI 是否已启动）。

    注意用 connect_ex 探测本机监听口是可靠的（立刻返回 0/10061）；
    ⚠ 别拿去探"对端握手"类的口——那种会因非阻塞返回 10035 而稳定误判。
    """
    import socket
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex(("127.0.0.1", int(port))) == 0
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _page_block_alpha() -> float:
    """页面里"实心块"改成多透明：有壁纸时几乎不透明，没壁纸时 0.35。

    为什么分情况：透明化的目的是让主题壁纸透出来，但壁纸一花，面板上的文字就糊在
    画面里（用户报「千恋万花·樱华主题看不清字」就是这个——那个主题的背景是角色
    拼贴画，而面板被压到 35% 不透明，字全部淹掉）。
    所以有壁纸 → 0.92（几乎不透明，仍能透出一点点氛围）；没壁纸 → 0.35（透出底色渐变）。
    """
    try:
        _btype, _src, _op = background_info()
        return 0.92 if _src else 0.35
    except Exception:
        return 0.35


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
    # 文字色：用来判断"这块是不是**实心强调色按钮 + 白字**"
    fg_re = re.compile(r"(?:^|;|\{)\s*color\s*:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|white)")

    def _color_of(txt: str):
        """'#rrggbb' / 'rgba(r,g,b,a)' → QColor（解析不了给 None）"""
        try:
            if txt.startswith("#"):
                return QColor(txt)
            inside = txt[txt.find("(") + 1:txt.rfind(")")]
            parts = [int(float(x)) for x in inside.split(",")[:3]]
            return QColor(*parts) if len(parts) == 3 else None
        except Exception:
            return None

    def _is_filled_accent(css: str) -> bool:
        """实心强调色按钮 + 白字：这种块压透明后会变成"淡底白字"看不清，必须保持不透明。

        ⚠ 必须扫**所有** color 声明：一个按钮的样式表里通常既有
          `QPushButton { background: 浅面; color: 主题文字色 }`
          又有 `QPushButton:checked { background: 强调色; color: white }`。
          只看第一处 color 会得出"文字是深色" → 漏判 → 选中态照样被压成淡蓝 + 白字
          （实测插件页选中胶囊 1.70:1）。
        """
        light_text = False
        for m in fg_re.finditer(css):
            v = m.group(1)
            c = QColor("#ffffff") if v == "white" else QColor(v)
            if c.isValid() and rel_luminance(c) >= 0.6:
                light_text = True
                break
        if not light_text:
            return False
        for m in hex_re.finditer(css):
            c = _color_of(m.group(2))
            if c is not None and c.isValid() and c.saturation() > 60:
                return True
        return False

    def _translucent(css: str) -> str:
        # ⚠ 实心强调色按钮（背景很彩 + 白字）**不许压透明**：压到 0.35 之后，
        #   浅色页面上会变成"淡蓝底 + 白字"（实测插件页选中胶囊 1.70:1、导入/刷新 1.72:1，
        #   白字糊在淡底上）。这类小控件本来也不需要透出壁纸。
        if _is_filled_accent(css):
            return css

        def _rep(m):
            head, col = m.group(1), m.group(2)
            try:
                if col.startswith("#"):
                    c = QColor(col)
                else:
                    parts = col[col.find("(") + 1:col.rfind(")")].split(",")
                    if len(parts) < 3:
                        return m.group(0)
                    nums = [int(float(x.strip())) for x in parts]
                    if len(parts) >= 4:
                        # alpha 有两种合法写法：0–1 小数、0–255 整数（Qt 都吃）。
                        # 早先只认小数写法，于是 rgba(...,120) 这种被判成"没带透明度"，
                        # 又被压成页面透明度 —— 颜色白丢一层（配色色块变淡就是这个根因）。
                        _raw_a = parts[3].strip()
                        _is_frac = ("." in _raw_a) or nums[3] <= 1
                        _a_now = nums[3] if _is_frac else nums[3] / 255.0
                        if _a_now < 1.0:
                            return m.group(0)                # 本来就半透明 → 不动
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
            if child.property("keep_true_color"):
                # 配色预览色块之类"必须显示真彩"的控件：跳过，别压透明度
                # （压到 35% 后几块颜色几乎一样，预览就失去意义了）
                continue
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


# 开屏最短展示时长：只为让淡入淡出动画看得见。窗口构造（各页面懒加载）本来就很快，
# 不要为了动画白等——旧值是写死的 900ms，等于每次打开启动器都白等近 1 秒。
_SPLASH_MIN_MS = 450


def launch() -> int:
    """启动器统一入口：全局样式 → 异常兜底 → 开屏动画 → 主窗口 → 事件循环。

    run_launcher.py 只负责环境准备（sys.path / Live2D DLL / Qt 插件路径 / OpenGL 格式），
    界面装配一律走这里，避免两个入口各写一遍、各走各的。
    """
    from PyQt5.QtWidgets import QApplication
    from . import silicon_ui as _sui
    from .colors import current_theme_id
    # ── 版本戳（排查"我打开的是不是新程序"用）─────────────────────────────
    # 打印**这份 silicon_window.py 的修改时间** + 程序目录 + 生效的启动器底色。
    # 换了新 exe 但看着没变化时，先看这一行：时间不对就是还在跑旧进程。
    try:
        import time as _tm
        from .colors import base_bg_color as _bbc, current_theme_id as _ctid0
        print("[PCL] 版本戳 %s｜程序目录 %s｜主题 %s｜启动器底色 %s"
              % (_tm.strftime("%m-%d %H:%M", _tm.localtime(os.path.getmtime(__file__))),
                 _app_base_dir(), _ctid0(), _bbc().name()))
    except Exception as _e:
        print(f"[PCL] ⚠ 版本戳打印失败: {_e}")
    # 首次运行生成空白 config.json（README 承诺过、代码里却一直没人做）：
    # 绿色版故意不带 config.json（隐私），但不生成的话，微信/QQ 入口读配置会
    # FileNotFoundError 秒退（用户实测"点启动微信秒卡退"）。只缺才建，绝不覆盖。
    try:
        from tool.config import ensure_config as _ensure_cfg
        _ensure_cfg(os.path.join(_app_base_dir(), "config.json"))
    except Exception as _e:
        print(f"[NewUI] ⚠ 生成 config.json 失败（继续）: {_e}")
    # ⚠ 必须在 QApplication 之前：让三个 Live2D 画布（工坊内嵌 / 实时预览窗口 / 调试器）
    #   共享 GL 上下文，否则第 2、3 个画布画不出模型（= 用户报的"崩坏 / 频闪"）。
    _sui.enable_shared_gl_contexts()
    app = QApplication.instance() or QApplication(sys.argv)

    # 全局异常兜底：未捕获异常只记日志并跳过，不让启动器整进程消失
    try:
        from . import safety as _safety
        _safety.install("launcher")
    except Exception as _e:
        print(f"[NewUI] ⚠ 全局异常兜底不可用: {_e}")

    # 全局样式（强调色跟随设置）：Silicon 外壳是当前唯一外壳，始终安装。
    # 旧代码写的是 `if current_theme_id() == "silicon"`，而主题默认值是 classic，
    # 结果默认配置下这套全局样式根本没装上（只有手动切到 silicon 主题才生效）。
    try:
        _acc = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#4c8dff")
        _sui.install(app, accent=_acc)
        print(f"[NewUI] 界面风格: {current_theme_id()} · 强调色 {ACCENT_ID} ({_acc})")
    except Exception as _e:
        print(f"[NewUI] ⚠ 全局样式加载失败: {_e}")

    splash = SplashScreen()
    splash.show()
    splash.fade(1.0, 260)
    splash.set_progress(25, "加载界面样式…")

    try:
        win = SiliconLauncher()
    except Exception:
        splash.close()      # 先收掉开屏，再把异常抛给入口记日志（不吞异常）
        raise

    def _ready():
        try:
            splash.set_progress(100, "准备就绪")
            win.show()
            QTimer.singleShot(160, lambda: splash.fade(0.0, 260, splash.close))
            QTimer.singleShot(120, lambda: _fade_window_in(win))
        except Exception as e:
            print(f"[NewUI] ⚠ 开屏收尾失败: {e}")
            try:
                win.show()
                splash.close()
            except Exception:
                pass

    QTimer.singleShot(_SPLASH_MIN_MS, _ready)
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
        print(f"[NewUI] ⚠ 主窗淡入失败: {e}")
