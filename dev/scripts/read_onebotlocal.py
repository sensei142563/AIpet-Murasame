# -*- coding: utf-8 -*-
"""读 OneBotLocal.kt 的关键部分：去重、ring 溢出、缓存读写、连接生命周期。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/bot/chat/OneBotLocal.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
print("共 %d 行" % len(lines))
print()
print("=== 与去重/缓存/ring 相关的行（带行号）===")
for i, l in enumerate(lines, 1):
    if re.search(r"messageId|seen|dedup|去重|ring|sessions\.|removeAt|removeFirst|takeLast|"
                 r"cacheFile|writeText|readText|MAX|LIMIT|40|200|trim", l):
        print("%4d| %s" % (i, l.rstrip()[:140]))
