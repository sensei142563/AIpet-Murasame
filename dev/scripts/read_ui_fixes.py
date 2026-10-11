# -*- coding: utf-8 -*-
"""读：① MemoryScreen 那三个按钮的布局块（导出/导入互通包 竖排问题）② 首页 QQ 卡里「打开 QQ 通道」的文案。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

ms = os.path.join(SRC, "ui/MemoryScreen.kt")
lines = io.open(ms, encoding="utf-8", errors="replace").read().split("\n")
print("=== MemoryScreen 155~200 行（按钮区）===")
for i in range(154, min(200, len(lines))):
    print("%4d| %s" % (i + 1, lines[i].rstrip()[:150]))

print()
print("=== 首页 QQ 卡「打开 QQ 通道」相关 ===")
for base, dirs, fs in os.walk(SRC):
    for f in fs:
        if not f.endswith(".kt"):
            continue
        p = os.path.join(base, f)
        ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        for i, l in enumerate(ls, 1):
            if "打开 QQ 通道" in l or "连不上电脑端" in l:
                print("   %s:%d" % (os.path.relpath(p, SRC), i))
                for k in range(max(0, i - 12), min(len(ls), i + 6)):
                    print("      %4d| %s" % (k + 1, ls[k].rstrip()[:140]))
                print()
