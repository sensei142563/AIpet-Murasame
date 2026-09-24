# -*- coding: utf-8 -*-
"""公共路径基准 — 统一「程序根目录」解析，杜绝 _internal/ 临时目录路径错位。

背景：
- 源码模式：__file__ 在项目根下的 tool/ 内 → 根 = dirname(dirname(__file__))
- exe 模式（PyInstaller onedir）：__file__ 在 _internal/ 内（会被 PyInstaller 解压），
  若用它推导数据目录 → 人脸/记忆/配置会写进 _internal/，重启后丢失或与子进程不同步。
  正确做法：exe 模式一律用「exe 所在目录」（可持久读写）。

用法：
    from tool.paths import app_base_dir, data_path
    FACE_DIR = data_path("face_shibie")
    CONFIG_PATH = data_path("config.json")
"""
import os
import sys


def app_base_dir() -> str:
    """程序根目录：
    - exe 模式 → exe 所在目录（持久可写，绿色版根）
    - 源码模式 → 项目根
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_path(*rel: str) -> str:
    """从程序根目录解析数据文件/目录的绝对路径（可传多段子路径）。"""
    return os.path.join(app_base_dir(), *rel)


def ensure_qt_plugin_path() -> None:
    """Qt 平台插件路径修复（中文/非 ASCII 安装路径，A 卡调试 §6）。

    PyQt5 5.15 在含中文等非 ASCII 的路径下按 Qt5Core.dll 推导插件目录时做 8 位转换，
    把路径算错（"下载"→"??"）导致找不到 platforms/qwindows.dll → 启动即崩溃。
    显式指定插件目录走宽字符 API；setdefault 不覆盖用户已有设置。
    必须放在任何 PyQt5 import / QApplication 构造之前调用（入口文件最顶部）。
    """
    try:
        import PyQt5 as _PyQt5
        _plugins = os.path.join(os.path.dirname(_PyQt5.__file__), "Qt5", "plugins")
        if os.path.isdir(_plugins):
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _plugins)
    except Exception:
        pass


def venv_python() -> str:
    """项目 runtime\\venv 的解释器（若存在），否则回落 sys.executable。

    子进程拉起 Python 服务（如 F5-TTS）时统一用本函数选解释器——避免系统 Python
    拉出缺库的"残缺实例"（A 卡调试 §9）。三入口 run.py / run_qq.py / run_wechat.py 共用。
    """
    try:
        p = os.path.join(app_base_dir(), "runtime", "venv", "Scripts", "python.exe")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return sys.executable


def project_python_path() -> str:
    """项目自带解释器的**确切路径**（不存在则空串）。

    与 `venv_python()` 的区别：那个会回落到 `sys.executable`（给子进程用），
    这里只在真的存在时返回，用来判断"我现在是不是跑在项目解释器上"。
    """
    p = os.path.join(app_base_dir(), "runtime", "venv", "Scripts", "python.exe")
    return p if os.path.exists(p) else ""


def ensure_project_python(script: str = "") -> bool:
    """确保当前进程用的是**项目自带解释器**（runtime\\venv）；不是就换过去并结束本进程。

    为什么必须有：用系统 Python 跑本项目入口 → 缺 PyQt5/torch 直接崩（Windows 事件日志里的
    MSVCP140 访问违规），而且会和正常桌宠抢 28565 端口 → 云端代理一断，桌宠就"没有任何回复"。
    `run.py`（桌宠）一直有这段逻辑，`run_launcher.py`（图形启动器）以前没有 —— 于是源码版
    用户按 README 敲 `python run_launcher.py`（系统 Python）会 ModuleNotFoundError: PyQt5。

    用法：入口文件（`run.py` / `run_launcher.py`）最顶部调一次。
    ⚠ 冻结版（PyInstaller exe）不适用：exe 不是 .py，换解释器没意义 → 直接返回。
    ⚠ Windows 上换解释器不能用 os.execv（实测换完会 segfault）：拉子进程后本进程退出。
    返回是否发生了切换（切换时本函数不会返回，因为 sys.exit(0)）。
    """
    try:
        if getattr(sys, "frozen", False):
            return False
        if os.environ.get("AIPET_REEXEC") == "1":       # 防无限重启
            return False
        venv = project_python_path()
        if not venv:
            return False
        cur = sys.executable or ""
        if os.path.normcase(venv) in os.path.normcase(cur):
            return False
        target = script or (sys.argv[0] if sys.argv else "")
        if not target or not os.path.isfile(target):
            return False
        if os.path.normcase(os.path.abspath(target)) == os.path.normcase(os.path.abspath(venv)):
            return False
        print(f"[AIpet] 当前解释器不是项目自带的（{cur}）→ 改用 {venv} 重新启动", flush=True)
        import subprocess
        env = dict(os.environ)
        env["AIPET_REEXEC"] = "1"
        subprocess.Popen([venv, os.path.abspath(target)] + list(sys.argv[1:]),
                         cwd=app_base_dir(), env=env)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[AIpet] ⚠ 切换项目解释器失败（继续用当前解释器）: {e}")
    return False