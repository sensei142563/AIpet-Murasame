# -*- coding: utf-8 -*-
"""读清设置流：ttsOn / voiceAddr 等是怎么从 MainActivity 流到 ChatScreen 与 SettingsPage 的。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")

FILES = ["MainActivity.kt", "ui/ChatScreen.kt", "ui/SettingsPage.kt"]
print("=== 1) MainActivity：设置状态与传递 ===")
p = os.path.join(SRC, "MainActivity.kt")
for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
    if re.search(r"ttsOn|ttsReady|voiceAddr|remember|SettingsPage\(|ChatScreen\(|load\(|gamesOn|voiceOn", l):
        print("   %4d| %s" % (i, l.strip()[:120]))

print()
print("=== 2) ChatScreen：参数与语音识别调用处 ===")
p = os.path.join(SRC, "ui/ChatScreen.kt")
lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
for i, l in enumerate(lines, 1):
    if re.search(r"^fun ChatScreen|ttsOn|recognizeWav|voiceOn|语音|mic|Mic|录|hold", l):
        print("   %4d| %s" % (i, l.strip()[:120]))

print()
print("=== 3) SettingsPage：参数与开关行样式 ===")
p = os.path.join(SRC, "ui/SettingsPage.kt")
for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
    if re.search(r"^fun SettingsPage|ttsOn|Switch|Row2\(|Checkbox|onTts", l):
        print("   %4d| %s" % (i, l.strip()[:120]))

print()
print("=== 4) recognizeWav 调用点上下文（ChatScreen 580-615）===")
p = os.path.join(SRC, "ui/ChatScreen.kt")
lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
for i in range(578, min(len(lines), 616)):
    print("   %4d| %s" % (i + 1, lines[i].rstrip()[:124]))
