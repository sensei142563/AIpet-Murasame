# -*- coding: utf-8 -*-
"""① section_title 的写死白字 → 跟随主题（Color1），深色主题退回原亮色
   ② 「控制台查看」链接的默认蓝 → 跟随主题（设 QLabel 调色板的 Link 颜色）
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

# ---------- ① section_title ----------
P1 = os.path.join(ROOT, "pcl_launcher", "silicon_ui.py")
t1 = io.open(P1, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD1 = '''    lbl = QLabel(f"<span style='color:{accent};'>▍</span> {text}")
    lbl.setStyleSheet(f"color: #e6eaf2; font-family: '{M.font}';"
                      f" font-size: 15px; font-weight: bold; padding: 2px 0;")
    return lbl'''
NEW1 = '''    # ★ 2026-10-14 修（主人："首页有一些字被写死成白色"）：
    #   这里原来把标题色**写死**成 #e6eaf2（浅灰白）—— 在深色主题上没问题，
    #   但换到浅色主题（千恋万花·樱华 / 沫子的日常，Color8=#fdf6ee）就是
    #   **白字叠在浅粉卡片上**，整行看不见（只剩左边那根 accent 竖条）。
    #   改成跟随主题正文色 Color1（浅色主题=深棕，深色主题=亮色）；取不到再退回明暗判断。
    try:
        from .colors import Color1 as _C1
        _title_color = _C1.name()
    except Exception:
        _title_color = "#e6eaf2" if _is_dark_theme() else "#2b3245"
    lbl = QLabel(f"<span style='color:{accent};'>▍</span> {text}")
    lbl.setStyleSheet(f"color: {_title_color}; font-family: '{M.font}';"
                      f" font-size: 15px; font-weight: bold; padding: 2px 0;")
    return lbl'''
if OLD1 in t1:
    t1 = t1.replace(OLD1, NEW1, 1)
    io.open(P1, "w", encoding="utf-8", newline="\n").write(t1)
    print("✓ ① section_title 已改为跟随主题（Color1）")
else:
    print("✗ ① 锚点未命中")
try:
    py_compile.compile(P1, doraise=True)
    print("   ✓ py_compile OK")
except Exception as e:
    print("   ✗ py_compile: %s" % e)
    sys.exit(1)

# ---------- ② 余额链接颜色 ----------
P2 = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
t2 = io.open(P2, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD2 = """                _u = console_url_for_model(str(model))
                if _u:
                    bal_lbl.setToolTip("点击打开控制台（余额 / 用量在那里看）：\\n%s" % _u)"""
NEW2 = """                _u = console_url_for_model(str(model))
                # ★ 2026-10-14：Qt 富文本里的 <a> 用**调色板的 Link 角色**上色，
                #   不认 style 里的 color ⇒ 浅色主题下会变成突兀的默认蓝。
                #   这里显式把 Link 颜色设成我们算好的主题色。
                try:
                    from PyQt5.QtGui import QPalette as _QP, QColor as _QC
                    _pal = bal_lbl.palette()
                    _pal.setColor(_QP.Link, _QC(color))
                    _pal.setColor(_QP.LinkVisited, _QC(color))
                    bal_lbl.setPalette(_pal)
                except Exception:
                    pass
                if _u:
                    bal_lbl.setToolTip("点击打开控制台（余额 / 用量在那里看）：\\n%s" % _u)"""
if OLD2 in t2:
    t2 = t2.replace(OLD2, NEW2, 1)
    io.open(P2, "w", encoding="utf-8", newline="\n").write(t2)
    print("✓ ② 余额链接改为主题色（不再默认蓝）")
else:
    print("✗ ② 锚点未命中")
try:
    py_compile.compile(P2, doraise=True)
    print("   ✓ py_compile OK")
except Exception as e:
    print("   ✗ py_compile: %s" % e)
    sys.exit(1)
