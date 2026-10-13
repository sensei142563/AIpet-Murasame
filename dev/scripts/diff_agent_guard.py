# -*- coding: utf-8 -*-
"""对比「agent 任务同时只跑一个 + 确认框」这段：备份里的实现 vs 当前树的现状。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"

r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % REF_BAK],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
bak = (r.stdout or "").split("\n")
i = next((k for k, l in enumerate(bak) if "我还在做上一件事" in l), None)
print("=== 备份里的这一段（约 100 行）===")
if i is not None:
    for j in range(max(0, i - 40), min(len(bak), i + 60)):
        print("   %5d| %s" % (j + 1, bak[j].rstrip()[:135]))

print()
print("=== 当前树里对应功能的现状（搜 agent 任务入口 / 确认 / isRunning）===")
cur = io.open(os.path.join(ROOT, "classes", "murasame_class.py"), encoding="utf-8",
              errors="replace").read().split("\n")
PAT = re.compile(r"agent|Agent|_worker|isRunning|QMessageBox|确认|问她|要不要|让她")
shown = 0
for k, l in enumerate(cur, 1):
    if PAT.search(l):
        print("   %5d| %s" % (k, l.strip()[:135]))
        shown += 1
        if shown > 55:
            print("   …（更多略）")
            break
