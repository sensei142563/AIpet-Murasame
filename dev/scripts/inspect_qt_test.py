# -*- coding: utf-8 -*-
"""查 test_qt_lifecycle.py:60 期待的两句文案在源码里是什么样（被改写还是丢了）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"

T = os.path.join(ROOT, "tests", "test_qt_lifecycle.py")
lines = io.open(T, encoding="utf-8", errors="replace").read().split("\n")
print("=== 测试第 48~70 行 ===")
for i in range(47, min(70, len(lines))):
    print("   %4d| %s" % (i + 1, lines[i].rstrip()[:130]))

KEYS = ("我还在做上一件事", "要让她去做吗", "上一件事", "正在做", "还在做", "忙")
print()
print("=== 当前树里含这些关键词的行 ===")
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dev\\scripts\\")
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in SKIP):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        for i, l in enumerate(t.split("\n"), 1):
            if "上一件事" in l or "要让她去做吗" in l:
                print("   %-42s %5d| %s" % (f, i, l.strip()[:110]))

print()
print("=== 覆盖前备份里同样的关键词 ===")
r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % REF_BAK],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
bak = r.stdout or ""
for i, l in enumerate(bak.split("\n"), 1):
    if "上一件事" in l or "要让她去做吗" in l:
        print("   backup murasame_class.py %5d| %s" % (i, l.strip()[:110]))
