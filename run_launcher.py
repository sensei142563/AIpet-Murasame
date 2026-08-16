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
from pcl_launcher.main_window import PCLMainWindow


def main():
    # OpenGL 格式设置（支持 Live2D 预览）
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    fmt.setSamples(0)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    try:
        window = PCLMainWindow()
        window.show()
        print("[Launcher] 窗口已显示，进入事件循环...")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 1

    return app.exec_()


if __name__ == "__main__":
    main()
