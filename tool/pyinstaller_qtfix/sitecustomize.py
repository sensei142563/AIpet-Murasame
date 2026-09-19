# -*- coding: utf-8 -*-
"""让 PyInstaller 在「非 ASCII 路径」下也能正确收集 PyQt5。

背景（实机踩到的坑）：
    PyQt5 的 QLibraryInfo.location() 把 Qt 内部（其实是对的）路径转成 Python str 时
    按 latin-1 解码 → 项目放在 "D:\\下载\\..." 这类中文目录时，Python 侧拿到的是
        D:/ÏÂÔØ/AI×À³è/.../PyQt5/Qt5/plugins
    这种乱码。PyInstaller 的 hook-PyQt5.QtWidgets 拿它去 os.path.isdir() 判为不存在 →
    直接抛 "Qt plugin directory '...' does not exist!"，打不出启动器；
    就算硬打包出来，产物里也会缺掉整个 PyQt5 → 用户双击 exe 弹
    "DLL load failed while importing QtWidgets: 找不到指定的模块"（本文件诞生的原因）。

做法：
    给 QLibraryInfo.location / path 套一层：拿到的路径先按 "latin-1 → GBK" 还原，
    只有还原结果确实是存在的目录时才采用；本来就正常的中文路径（latin-1 编不回去）
    原样返回，绝不误伤。

启用方式（由 build_launcher.py 自动设置，不污染 site-packages）：
    set PYTHONPATH=<本目录>  &  set AIPET_QT_PATHFIX=1
"""
import os

if os.environ.get("AIPET_QT_PATHFIX") == "1":
    def _repair(p):
        """把被按 latin-1 误解码的路径还原成真路径；判断不了就原样返回"""
        if not isinstance(p, str) or os.path.isdir(p):
            return p
        try:
            fixed = p.encode("latin-1").decode("gbk")
        except Exception:
            return p                      # 正常的中文路径编不成 latin-1 → 不动它
        return fixed

    def _install():
        try:
            from PyQt5.QtCore import QLibraryInfo
        except Exception:
            return False
        for _name in ("location", "path"):    # Qt5 用 location()，Qt6 用 path()
            _orig = getattr(QLibraryInfo, _name, None)
            if _orig is None or getattr(_orig, "_aipet_wrapped", False):
                continue
            def _make(orig):
                def _wrapped(which):
                    return _repair(orig(which))
                _wrapped._aipet_wrapped = True
                return _wrapped
            try:
                setattr(QLibraryInfo, _name, staticmethod(_make(_orig)))
            except Exception:
                pass
        return True

    _install()
