# -*- coding: utf-8 -*-
"""Live2D 表情 / 动作调试器 —— 命令行入口（实现已经搬到 `pcl_launcher/live2d_debugger.py`）。

用途：逐个查看角色模型的表情(exp3) / 动作(motion3) 效果，并**给它们打标签**，
      再照着标签配 pet.json 的表情/动作映射。
      立绘工坊的 Live2D 区也有按钮直接打开（不用敲命令）。

用法：
    python debug_live2d.py [--pet noir]
    （不带参数默认当前活动角色；窗口里可切换任何带 Live2D 模型的本机角色）

⚠ 这个文件以前是"临时简陋版"的独立实现，现在是薄入口：所有界面/逻辑都在
  `pcl_launcher/live2d_debugger.py`（单一定义，命令行与启动器里看到的是同一个东西）。
"""

try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji 会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import argparse
import os
import sys

# ==== Qt 平台插件路径修复（中文/非 ASCII 路径，A 卡调试 §6）====
# 必须在任何 PyQt5 / Live2d（内部 import PyQt5）之前
try:
    from tool.paths import ensure_qt_plugin_path
    ensure_qt_plugin_path()
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# ==== Live2D DLL 路径（复用 Live2d 模块顶部的设置）====
import Live2d.live2d_ui as _lui  # noqa: E402,F401  （顶部已设置 PATH / add_dll_directory）

from PyQt5.QtWidgets import QApplication  # noqa: E402

from pets.pet_registry import get_active_pet_id  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Live2D 表情/动作调试器（可打标签）")
    parser.add_argument("--pet", default="",
                        help="角色 ID（如 noir / murasame / arona / hiyori），默认当前活动角色")
    args = parser.parse_args()
    pet = args.pet or get_active_pet_id()

    # ⚠ 必须在 QApplication 之前：调试器 + 实时预览窗口会在同一进程里各建一个
    #   Live2D 画布，不共享 GL 上下文的话后建的那个画不出模型（"崩坏 / 频闪"）。
    from pcl_launcher import silicon_ui as _sui_pre
    _sui_pre.enable_shared_gl_contexts()
    app = QApplication(sys.argv)
    from pcl_launcher import silicon_ui
    silicon_ui.install(app)
    from pcl_launcher.live2d_debugger import open_debugger

    dlg = open_debugger(pet)
    if dlg is None:
        print("[debug] 打开调试器失败（看上面的报错）")
        return 1
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
