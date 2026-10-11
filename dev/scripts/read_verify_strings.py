# -*- coding: utf-8 -*-
"""读准 5 条"只能真机验证"项所需的判据字符串（日志原文 / 文件格式）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

TARGETS = [
    ("ui/SileroVad.kt", r"Silero VAD ready"),
    ("bot/chat/VoiceClient.kt", r"通知调用方回退系统 TTS"),
    ("bot/chat/VoiceClient.kt", r"未提供 onGiveUp"),
    ("bot/chat/OneBotLocal.kt", r"丢弃重复消息"),
    ("SecureStore.kt", r"isEncrypted|fun encrypt|SEP|sep|v1"),
    ("Store.kt", r'AssetSeed|\.part|pet_list'),
]
for rel, pat in TARGETS:
    p = os.path.join(SRC, rel.replace("/", os.sep))
    print("=== %s  ⇐ /%s/ ===" % (rel, pat))
    if not os.path.isfile(p):
        print("   ✗ 文件不存在")
        continue
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(pat, l):
            print("   %4d| %s" % (i, l.strip()[:150]))
    print()
