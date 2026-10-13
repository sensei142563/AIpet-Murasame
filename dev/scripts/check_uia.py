# -*- coding: utf-8 -*-
"""查 comtypes/UIA 在两个解释器里的可用性，并列出 UIA 缺失会影响哪些功能。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
PROBE = '''
import sys
print("exe =", sys.executable)
print("prefix =", sys.prefix)
for name in ("comtypes", "comtypes.client", "uiautomation", "win32com", "pilk", "pynput"):
    try:
        __import__(name)
        print("  %-18s 有" % name)
    except Exception as e:
        print("  %-18s 缺 (%s)" % (name, type(e).__name__))
try:
    from comtypes.gen import UIAutomationClient as UIA
    print("  UIAutomationClient 有")
except Exception as e:
    print("  UIAutomationClient 缺 (%s)" % type(e).__name__)
'''

p = os.path.join(ROOT, "dev", "scripts", "_probe_uia.py")
io.open(p, "w", encoding="utf-8", newline="\n").write(PROBE)

for exe in (os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
            sys.executable):
    print("=" * 74)
    print("=== %s ===" % exe)
    r = subprocess.run([exe, p], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
        if l.strip() and "Warning" not in l and "pkg_resources" not in l:
            print("   " + l.strip()[:130])

print()
print("=== 直接跑项目自带的 UIA 自检（tool/uia.py 有 __main__） ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tool", "uia.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=300, cwd=ROOT)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines()[-12:]:
    print("   " + l.strip()[:140])
