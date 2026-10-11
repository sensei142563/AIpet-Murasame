# -*- coding: utf-8 -*-
"""① ⑨4 dry-run 不谎报；② 启动真机验收（后台）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old = '''    record("⑨4 前台守卫", "PASS",'''
new = '''    record("⑨4 前台守卫", "SKIP" if DRY else "PASS",'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ⑨4 已改为 dry-run 下 SKIP")
else:
    print("· 已是 SKIP 或锚点不同")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   语法:", "OK" if r.returncode == 0 else "FAIL")
print()
print("=== 启动真机验收（后台）===")
