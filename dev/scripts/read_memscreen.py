# -*- coding: utf-8 -*-
"""① 读 MemoryScreen 里「导入互通包」相关代码（定位竖排文字的排版问题）
   ② 给底部导航加显式 bottom padding（华为手势导航不报 inset，只能显式抬）
   ③ 编译 + 装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
MEM = os.path.join(SRC, "ui/MemoryScreen.kt")
MAIN_ACT = os.path.join(SRC, "MainActivity.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== MemoryScreen 里与「互通/导入/导出」相关的行 ===")
lines = io.open(MEM, encoding="utf-8", errors="replace").read().split("\n")
hits = [i for i, l in enumerate(lines)
        if re.search(r"互通|导入|导出|Import|Export|memory_transfer|包", l)]
for i in hits:
    lo, hi = max(0, i - 6), min(len(lines), i + 8)
    print("   ---- 行 %d 附近 ----" % (i + 1))
    for k in range(lo, hi):
        mark = ">>" if k == i else "  "
        print("   %s%4d| %s" % (mark, k + 1, lines[k].rstrip()[:135]))
    print()
    if len(hits) > 2 and i == hits[2]:
        break
