"""
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

# Qt 平台插件路径修复（中文/非 ASCII 路径，A 卡调试 §6）——必须在 PyQt5 import 前
try:
    from tool.paths import ensure_qt_plugin_path
    ensure_qt_plugin_path()
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
