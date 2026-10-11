# -*- coding: utf-8 -*-
"""读 OneBotParse.kt 与 OneBotLocal 里调用它的地方（对抗测试前置）。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
F = os.path.join(SRC, "bot/chat/OneBotParse.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("=== OneBotParse.kt（共 %d 行）===" % len(lines))
for i, l in enumerate(lines, 1):
    print("%4d| %s" % (i, l.rstrip()))
