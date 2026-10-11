# -*- coding: utf-8 -*-
"""读准设置页「测试电脑语音」那行的真实文本，插入离线合成开关行。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")

s = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
for i, l in enumerate(s.split("\n"), 1):
    if "测试电脑语音" in l or "离线音色" in l or "点一下测试" in l or "识别自检" in l:
        print("%4d| %s" % (i, l.rstrip()[:150]))
print()
i = s.find("测试电脑语音")
print("=== 上下文 ===")
print(s[max(0, i - 400):i + 500])
