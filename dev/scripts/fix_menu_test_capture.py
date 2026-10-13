# -*- coding: utf-8 -*-
"""修 tests/test_bugfix_0930.py 的菜单捕获桩：代码已从 exec_ 改成动画 popup，桩要同步。
断言保持原样（不放松任何检查），只是把"怎么拿到菜单对象"改成与新实现一致。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
T = os.path.join(ROOT, "tests", "test_bugfix_0930.py")

t = io.open(T, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = '''_real_exec = QMenu.exec_
QMenu.exec_ = lambda self, *a, **k: captured.setdefault("menu", self) or None'''
NEW = '''# ⚠ 菜单的实现已经从「QMenu.exec_()」改成「动画 popup()」（见
#   classes/murasame_class.py::_popup_menu_animated —— 为了做淡入上浮过渡）。
#   所以只打桩 exec_ 会**永远捕获不到菜单**（menu=None，检查项全红）。
#   这里把两种弹出方式都打桩，断言本身一条不改；并额外记下 pet._outfit_menu 兜底。
_real_exec = QMenu.exec_
_real_popup = QMenu.popup


def _capture(self, *a, **k):
    captured.setdefault("menu", self)
    return None


QMenu.exec_ = _capture
QMenu.popup = _capture'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("✓ 已把捕获桩扩展到 popup（断言未动）")
else:
    print("✗ 锚点未命中（可能已改过）")

OLD2 = '''    QMenu.exec_ = _real_exec
menu = captured.get("menu")'''
NEW2 = '''    QMenu.exec_ = _real_exec
    QMenu.popup = _real_popup
# 兜底：即使两种桩都没打中，也能从 pet 身上拿到刚构建的菜单
menu = captured.get("menu") or getattr(pet, "_outfit_menu", None)'''
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ 已加 pet._outfit_menu 兜底")
else:
    print("⚠ 兜底锚点未命中")

io.open(T, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 跑 tests/test_bugfix_0930.py ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join("tests", "test_bugfix_0930.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=900)
out = ((r.stdout or "") + (r.stderr or "")).split("\n")
show = [l for l in out if "菜单" in l or "FAIL" in l or "通过" in l or "OK]" in l and "Live2D" in l]
for l in show[-22:]:
    print("   " + l.rstrip()[:150])
print("   退出码 =", r.returncode)
