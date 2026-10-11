# -*- coding: utf-8 -*-
"""读：① ChatScreen 的语音输入路径（长按说话 → recognizeWav / 系统识别）② OnlineAsr 的 API 与调用点。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
CS = os.path.join(SRC, "ui/ChatScreen.kt")

lines = io.open(CS, encoding="utf-8", errors="replace").read().split("\n")
print("=== ChatScreen 560~700 行（语音输入区）===")
for i in range(559, min(700, len(lines))):
    print("%5d| %s" % (i + 1, lines[i].rstrip()[:150]))

print()
print("=== 全工程 OnlineAsr 使用点 ===")
for base, dirs, fs in os.walk(SRC):
    for f in fs:
        if f.endswith(".kt"):
            p = os.path.join(base, f)
            for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
                if "OnlineAsr" in l:
                    print("   %-40s %4d| %s" % (os.path.relpath(p, SRC), i, l.strip()[:120]))

print()
print("=== OnlineAsr.kt 的公开函数签名 ===")
oa = os.path.join(SRC, "ui/OnlineAsr.kt")
if os.path.isfile(oa):
    for i, l in enumerate(io.open(oa, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"^\s*(fun|object|class|@Volatile|private const|init\s*\{)", l):
            print("   %4d| %s" % (i, l.rstrip()[:130]))
else:
    print("   （不在 ui/ 下，搜索）")
    for base, dirs, fs in os.walk(SRC):
        for f in fs:
            if f == "OnlineAsr.kt":
                print("   实际路径：", os.path.relpath(os.path.join(base, f), SRC))
