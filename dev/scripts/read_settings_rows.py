# -*- coding: utf-8 -*-
"""设置页：加「离线识别（实验）」开关行 + 让「识别自检」行显示当前状态。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")

src = io.open(SP, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = src.split("\n")
print("=== SettingsPage 60~110 行（看清 Row2 与 state）===")
for i in range(59, min(112, len(lines))):
    print("%4d| %s" % (i + 1, lines[i].rstrip()[:145]))
