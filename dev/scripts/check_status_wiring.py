# -*- coding: utf-8 -*-
"""确证启动器「状态」页的接线（不动 UI，直接读代码 + 用 venv 解释器做导入级检查）。
输出：NAV 定义、status 分支指向哪个 panel、panel 类是否存在、是否能被导入。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SW = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
SP = os.path.join(ROOT, "pcl_launcher", "status_panel.py")

print("=== ① silicon_window.py 里的 NAV 与 status 接线 ===")
lines = io.open(SW, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(lines, 1):
    s = l.strip()
    if re.search(r"\bNAV\b\s*=", s) or '"status"' in s or "status_panel" in s \
            or "StatusPanel" in s or "status_page_enabled" in s:
        print("   %6d| %s" % (i, s[:118]))

print()
print("=== ② status_panel.py 里定义了哪些类/函数 ===")
sp = io.open(SP, encoding="utf-8", errors="replace").read()
for m in re.finditer(r"(?m)^(class\s+\w+|def\s+\w+)", sp):
    print("   " + m.group(0))

print()
print("=== ③ 用 venv 解释器做导入级检查（不建窗口）===")
code = (
    "import sys, io\n"
    "sys.path.insert(0, r'%s')\n"
    "import importlib\n"
    "m = importlib.import_module('pcl_launcher.status_panel')\n"
    "names = [n for n in dir(m) if not n.startswith('_')]\n"
    "print('   status_panel 导入成功 ✓ 公开名:', ', '.join(names[:14]))\n"
) % ROOT
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"), "-c", code],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
out = (r.stdout or "").strip()
err = (r.stderr or "").strip()
print(out if out else "   （无输出）")
if err:
    print("   stderr:", err.splitlines()[-1][:160] if err.splitlines() else "")
print("   rc =", r.returncode)
