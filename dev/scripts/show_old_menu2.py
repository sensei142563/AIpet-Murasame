# -*- coding: utf-8 -*-
"""打印「覆盖前」右键菜单的完整构造代码（找 输入对话 所在区域），用于对照现在的菜单。"""
import io
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF = "remotes/origin/backup/main-before-overwrite-20261001"

r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % REF],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
t = r.stdout or ""
lines = t.split("\n")
idx = [i for i, l in enumerate(lines) if "输入对话" in l]
print("=== 旧版里 '输入对话' 出现在 %d 处 ===" % len(idx))
for i in idx[:4]:
    lo, hi = max(0, i - 25), min(len(lines), i + 12)
    print("-" * 76)
    for j in range(lo, hi):
        print("%5d| %s" % (j + 1, lines[j].rstrip()[:145]))
