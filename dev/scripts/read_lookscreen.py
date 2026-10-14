# -*- coding: utf-8 -*-
"""① 读「主人让我看屏幕」的执行现场
   ② 加两道闸：每轮硬上限 + 遇到 403/404 就熔断（不再无限重试，并明确告知主人）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "classes", "murasame_class.py")
ls = io.open(P, encoding="utf-8", errors="replace").read().split("\n")

print("=== ① 「主人让我看屏幕」执行现场 ===")
start = next((i for i, l in enumerate(ls) if "主人让我看屏幕 → 当场抓屏识别" in l), None)
if start is None:
    print("   ✗ 没找到")
    sys.exit(1)
for i in range(start - 2, min(len(ls), start + 60)):
    print("   %5d| %s" % (i + 1, ls[i].rstrip()[:118]))

print()
print("=== ② 找视觉调用与失败分支 ===")
for i, l in enumerate(ls, 1):
    if re.search(r"视觉识别没返回内容|退回普通回答|_look_screen|看屏幕|抓屏", l):
        print("   %5d| %s" % (i, l.strip()[:112]))
