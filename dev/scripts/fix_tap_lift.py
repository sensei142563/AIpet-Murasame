# -*- coding: utf-8 -*-
"""兜底也抬高 60px（首页那种找不到 clickable 祖先的情况），然后立即重跑真机验收（后台）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "def tap_text(xml, needle, wait=2.5, lift=0):" in t:
    t = t.replace("def tap_text(xml, needle, wait=2.5, lift=0):",
                  "def tap_text(xml, needle, wait=2.5, lift=60):", 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 兜底 lift 改为 60px（找不到 clickable 祖先时不再点最底边）")
else:
    print("· 已是 lift=60 或锚点不同")
    print([l for l in t.split("\n") if "def tap_text(" in l])

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   语法:", "OK" if r.returncode == 0 else "FAIL")
print()
print("=== 启动真机验收（后台）===")
