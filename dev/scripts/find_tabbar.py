# -*- coding: utf-8 -*-
"""定位底部导航条：找"首页/记忆/人设/设置/聊天"这 5 个标签同时出现在同一小段代码里的地方。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

LABELS = ["首页", "记忆", "人设", "设置", "聊天"]
pat = re.compile("|".join(LABELS))
files = []
for base, dirs, fs in os.walk(SRC):
    for f in fs:
        if f.endswith(".kt"):
            files.append(os.path.join(base, f))

print("=== 同一文件里 5 个标签都出现且彼此靠近的文件 ===")
for p in files:
    lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    hits = [i for i, l in enumerate(lines) if pat.search(l)]
    if len(hits) < 4:
        continue
    # 找一段窗口内命中 >=4 的地方
    for i in hits:
        window = [h for h in hits if i <= h <= i + 60]
        if len(window) >= 4:
            print("   %-40s 行 %d~%d（命中 %d 个标签）" % (os.path.relpath(p, SRC), i + 1, window[-1] + 1, len(window)))
            for k in range(max(0, i - 12), min(len(lines), i + 34)):
                print("      %4d| %s" % (k + 1, lines[k].rstrip()[:145]))
            print()
            break
