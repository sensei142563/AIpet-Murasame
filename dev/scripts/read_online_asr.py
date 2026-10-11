# -*- coding: utf-8 -*-
"""给离线识别（SenseVoice 原生库）加总开关：
  ① OnlineAsr：offlineEnabled(ctx)（默认关，files/asr_offline_enabled.txt 写 1 才开）
     init()/selfTest() 开头判断，停用时**根本不碰原生库**
  ② ChatScreen 长按说话：停用时自动改用系统识别（RecognizerIntent）
  ③ SettingsPage 自检按钮：停用时给出明确提示，不调用原生库
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
OA = os.path.join(SRC, "ui/OnlineAsr.kt")
CS = os.path.join(SRC, "ui/ChatScreen.kt")
SP = os.path.join(SRC, "ui/SettingsPage.kt")

oa = io.open(OA, encoding="utf-8").read().replace("\r\n", "\n")
print("=== OnlineAsr: init / recognizeWav / selfTest 现状 ===")
for pat in (r"fun init\(", r"fun recognizeWav\(", r"fun selfTest\("):
    m = re.search(pat, oa)
    if m:
        seg = oa[m.start():m.start() + 700]
        print("---- %s ----" % pat)
        print("\n".join("   " + l[:150] for l in seg.split("\n")[:18]))
        print()
