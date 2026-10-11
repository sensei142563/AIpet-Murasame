# -*- coding: utf-8 -*-
"""读 ChatScreen 初始化块（315~400 行）与 ASR/TTS 引擎创建点，为细粒度埋点做准备。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
CS = os.path.join(SRC, "ui/ChatScreen.kt")
lines = io.open(CS, encoding="utf-8", errors="replace").read().split("\n")

print("=== ChatScreen 300~400 行 ===")
for i in range(299, min(400, len(lines))):
    print("%5d| %s" % (i + 1, lines[i].rstrip()[:152]))

print()
print("=== OnlineAsr / SileroVad / OfflineTts / 引擎创建相关行（全文件）===")
for i, l in enumerate(lines, 1):
    if re.search(r"OnlineAsr|SileroVad|OfflineTts|selfTest|VoiceClient|engine\s*=|TextToSpeech|"
                 r"Dispatchers\.IO|withContext|LaunchedEffect|DisposableEffect", l):
        print("%5d| %s" % (i, l.rstrip()[:150]))
