# -*- coding: utf-8 -*-
"""读 OneBotLocal 的 handle()、缓存存取、去重相关块的确切实现。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/bot/chat/OneBotLocal.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
for a, b, title in ((36, 60, "字段与常量"), (120, 175, "handle() 与去重"),
                    (238, 275, "缓存写入与恢复")):
    print("=== %s（%d~%d）===" % (title, a, b))
    for i in range(a - 1, min(len(lines), b)):
        print("%4d| %s" % (i + 1, lines[i].rstrip()[:150]))
    print()
