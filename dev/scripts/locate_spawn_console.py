# -*- coding: utf-8 -*-
"""查 test_qt_lifecycle 的 B1 段（_spawn_console / _watch_child）与本树现状。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF = "remotes/origin/backup/main-before-overwrite-20261001"

T = os.path.join(ROOT, "tests", "test_qt_lifecycle.py")
lines = io.open(T, encoding="utf-8", errors="replace").read().split("\n")
s = next((i for i, l in enumerate(lines) if "B1)" in l), None)
print("=== 测试 B1 段（第 %s 行起）===" % (s + 1 if s is not None else "?"))
if s is not None:
    for j in range(s, min(len(lines), s + 30)):
        print("   %4d| %s" % (j + 1, lines[j].rstrip()[:135]))

print()
print("=== 本树里 _spawn_console / _watch_child 的定义与使用 ===")
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dev\\scripts\\")
for dp, dn, fn in os.walk(ROOT):
    if any(x in dp + "\\" for x in SKIP):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        for i, l in enumerate(t.split("\n"), 1):
            if "_spawn_console" in l or "_watch_child" in l or "CREATE_NEW_CONSOLE" in l:
                print("   %-28s %5d| %s" % (f, i, l.strip()[:120]))
