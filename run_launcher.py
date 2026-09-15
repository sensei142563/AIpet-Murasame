"""
PCL 风格 AIpet 启动器入口
双击 run_launcher.py 或运行: python run_launcher.py
"""

import os
import sys

# 添加父目录到 sys.path，确保能导入 pcl_launcher
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 如果在 pcl_launcher 目录内运行，切回上级目录
if os.getcwd().endswith('pcl_launcher'):
    os.chdir(os.path.dirname(os.getcwd()))

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

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QSurfaceFormat
# 不再导入旧版主窗口（PCLMainWindow 已随旧界面下线）：
# 那个导入会连带拉起 widgets.py 等重模块 → 启动变慢；
# 新版外壳的各页面改为「进哪个才建哪个」的懒加载。


def main():
    # OpenGL 格式设置（支持 Live2D 预览）
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(0)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    # ===== 全局异常兜底：未捕获异常只记日志并跳过，不再让启动器整进程消失 =====
    try:
        from pcl_launcher import safety as _safety
        _safety.install("launcher")
    except Exception as _e:
        print(f"[PCL] ⚠ 全局异常兜底不可用: {_e}")

    # ===== Silicon 新界面：全局样式（强调色跟随主题设置）=====
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from pcl_launcher import silicon_ui
        from pcl_launcher.colors import ACCENT_ID, THEME_COLORS, current_theme_id
        _acc = "#4c8dff"
        try:
            _acc = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", _acc)
        except Exception:
            pass
        silicon_ui.install(app, accent=_acc)
        print(f"[PCL] 界面风格: {current_theme_id()} · 强调色 {ACCENT_ID} ({_acc})")
    except Exception as _e:
        print(f"[PCL] ⚠ 新界面样式加载失败（回退旧样式）: {_e}")

    def _dbg(msg):
        try:
            import os as _os
            base = _os.path.dirname(_os.path.abspath(__file__))
            with open(_os.path.join(base, "data", "launcher_start.log"), "a", encoding="utf-8") as f:
                import datetime as _dt
                f.write(f"{_dt.datetime.now():%H:%M:%S} {msg}\n")
        except Exception:
            pass

    try:
        _dbg("构造启动器窗口前")
        # ===== 外壳选择：新版 Silicon 界面（默认）/ 旧版界面（config.ui_shell）=====
        # 新版外壳（旧版界面已下线）
        _shell = "silicon"
        from pcl_launcher.silicon_window import SiliconLauncher
        window = SiliconLauncher()
        _dbg(f"构造完成（外壳={_shell}）")
        window.show()
        _dbg("show 完成")
        print(f"[Launcher] 窗口已显示（{_shell}），进入事件循环...")
    except Exception as e:
        import traceback
        _dbg("构造异常: " + repr(e) + "\n" + traceback.format_exc())
        traceback.print_exc()
        return 1

    _dbg("进入 exec_")
    rc = app.exec_()
    _dbg(f"exec_ 返回 {rc}")
    return rc


if __name__ == "__main__":
    main()
