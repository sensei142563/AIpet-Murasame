# -*- coding: utf-8 -*-
"""读 ChatCore.kt 全文（对话主循环）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/bot/chat/ChatCore.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("共 %d 行" % len(lines))
for i, l in enumerate(lines, 1):
    print("%4d| %s" % (i, l.rstrip()))
