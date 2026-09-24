"""

# 本机地址绕过系统代理（挂加速器/梯子时代理会连 127.0.0.1 一起劫持 → "信号不正常"）
try:
    # 冻结版 exe 里程序目录还没进 sys.path → 先补上再导入（否则这段修复会被静默跳过，
    # 表现为"桌宠明明在运行，启动器却显示未运行/无法关闭"）
    import sys as _sys2, os as _os2
    _b2 = _os2.path.dirname(_os2.path.abspath(__file__))
    if _b2 not in _sys2.path:
        _sys2.path.insert(0, _b2)
    from tool.net_env import bypass_proxy_for_local as _bpfl
    _bpfl()
except Exception as _e2:
    print(f"[Launcher] 本机代理绕过设置失败（不影响启动）: {_e2}")

PCL 风格 AIpet 启动器入口
双击 run_launcher.py 或运行: python run_launcher.py
"""

try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji 会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
import sys

# 日志/重定向时 stdout 可能是 GBK，打印 ⚠ 之类的字符会抛 UnicodeEncodeError 把程序带崩
try:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")   # 子进程也安全
    os.environ.setdefault("PYTHONUTF8", "1")
except Exception:
    pass

# ── 界面日志落盘：启动器的全部输出同时写进 data/launcher_ui.log ──────────────
# 为什么需要：启动器是 GUI（打包版连控制台都没有），它打印的排查信息一闪就没 →
# 用户报"某个选项点了没反应"时，谁也看不到它到底走到哪一步了。这里包一层 Tee：
# 控制台照常打印，同时按行追加到程序目录下的 data/launcher_ui.log（每次启动留一行头）。
def _install_ui_log() -> None:
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, "frozen", False):
            _base = os.path.dirname(sys.executable)
        _d = os.path.join(_base, "data")
        os.makedirs(_d, exist_ok=True)
        _p = os.path.join(_d, "launcher_ui.log")
        _fobj = open(_p, "a", encoding="utf-8", errors="replace", buffering=1)
        import time as _t
        _fobj.write("\n===== %s 启动器启动（%s）=====\n"
                    % (_t.strftime("%Y-%m-%d %H:%M:%S"),
                       os.path.dirname(os.path.abspath(__file__))))

        class _Tee:
            def __init__(self, *streams):
                self._streams = [s for s in streams if s is not None]

            def write(self, s):
                for st in self._streams:
                    try:
                        st.write(s)
                    except Exception:
                        pass
                return len(s)

            def flush(self):
                for st in self._streams:
                    try:
                        st.flush()
                    except Exception:
                        pass

            def isatty(self):
                return False

        sys.stdout = _Tee(sys.stdout, _fobj)
        sys.stderr = _Tee(sys.stderr, _fobj)
        print("[Launcher] 界面日志 → %s" % _p)
    except Exception as _e:
        print("[Launcher] 界面日志不可用（继续）: %s" % _e)


try:
    _install_ui_log()
except Exception:
    pass

# 添加父目录到 sys.path，确保能导入 pcl_launcher
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 如果在 pcl_launcher 目录内运行，切回上级目录
if os.getcwd().endswith('pcl_launcher'):
    os.chdir(os.path.dirname(os.getcwd()))

# ⚠ 第二件事：确保用的是**项目自带解释器**（runtime\venv）——和 run.py 同一个道理：
#   用系统 Python 跑这个入口会 ModuleNotFoundError: PyQt5（README 里让源码版用户敲的
#   就是 `python run_launcher.py`，双击 .py 时更常见），而且缺 DLL 会直接崩。
#   检测到不对就用 venv 重新拉起自己（本进程退出，AIPET_REEXEC 防循环；冻结版自动跳过）。
try:
    from tool.paths import ensure_project_python as _ensure_py
    _ensure_py(__file__)
except Exception as _e:
    print(f"[AIpet] ⚠ 项目解释器检查不可用（继续用当前解释器）: {_e}")

# 必须在导入 live2d 之前设置 DLL 路径（和 Live2d/live2d_ui.py 一样）
import sys as _sys
import os as _os

if getattr(_sys, 'frozen', False):
    # PyInstaller --onefile 把所有 add-data 解压到 _MEIPASS
    dll_dir = _os.path.join(getattr(_sys, '_MEIPASS', _os.path.dirname(_sys.executable)), "Live2d")
else:
    dll_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "Live2d")

if _os.path.exists(dll_dir):
    _os.environ.setdefault("PATH", "")
    _os.environ["PATH"] = dll_dir + _os.pathsep + _os.environ["PATH"]
    try:
        _os.add_dll_directory(dll_dir)
    except Exception:
        pass

# ★ 让 Qt 找到多媒体后端插件（mediaservice）：缺了它 QMediaPlayer 直接不可用，
#   视频背景永远播不出来（用户反馈"视频背景不显示"）。源码/冻结两种布局都算一遍。
try:
    import PyQt5 as _pyqt5, os as _os3
    _pp = _os3.path.join(_os3.path.dirname(_pyqt5.__file__), "Qt5", "plugins")
    if _os3.path.isdir(_pp):
        _os3.environ.setdefault("QT_PLUGIN_PATH", _pp)
except Exception:
    pass

from PyQt5.QtGui import QSurfaceFormat
# 不再导入旧版主窗口（PCLMainWindow 已随旧界面下线）：
# 那个导入会连带拉起 widgets.py 等重模块 → 启动变慢；
# 新版外壳的各页面改为「进哪个才建哪个」的懒加载。


def main():
    # OpenGL 格式设置（支持 Live2D 预览）——必须在 QApplication 创建前
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(0)
    QSurfaceFormat.setDefaultFormat(fmt)

    def _dbg(msg):
        try:
            import datetime as _dt
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "data", "launcher_start.log"), "a", encoding="utf-8") as f:
                f.write(f"{_dt.datetime.now():%H:%M:%S} {msg}\n")
        except Exception:
            pass

    # ===== 界面装配全部交给 silicon_window.launch() =====
    # 全局样式 / 异常兜底 / 开屏动画 / 主窗口 / 事件循环都在那里。
    # 本文件只负责「环境准备」（sys.path、Live2D DLL、Qt 插件路径、OpenGL 格式）
    # 与启动日志——以前这里把装配逻辑又抄了一遍，结果两边逐渐走偏
    # （最典型：这里没开屏动画，那边全局样式又因为主题名判断写错而没装）。
    _dbg("调用 launch() 前")
    try:
        from pcl_launcher.silicon_window import launch
        rc = launch()
    except Exception as e:
        import traceback
        _dbg("launch() 异常: " + repr(e) + "\n" + traceback.format_exc())
        traceback.print_exc()
        return 1
    _dbg(f"launch() 返回 {rc}")
    return rc


if __name__ == "__main__":
    main()
