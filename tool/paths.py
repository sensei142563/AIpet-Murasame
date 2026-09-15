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