# -*- coding: utf-8 -*-
"""找 VoiceClient.speak 的调用点并传入 onGiveUp（系统 TTS 兜底），然后提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== VoiceClient.speak 的调用点（含上下文）===")
hits = []
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"VoiceClient\.speak\(", body):
            ln = body[:m.start()].count("\n") + 1
            lines = body.split("\n")
            ctx = "\n".join(lines[max(0, ln - 6):ln + 10])
            hits.append((os.path.relpath(fp, SRC), ln, ctx))
for rel, ln, ctx in hits:
    print("   %s:%d" % (rel, ln))
    for l in ctx.split("\n"):
        print("      " + l.rstrip()[:130])
    print("   ---")

print()
print("=== 系统 TTS 是怎么调的（找现成的兜底函数）===")
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"(TextToSpeech|systemTts|speakSystem|系统朗读|TTSService)[^\n]{0,80}", body):
            print("   %-34s %s" % (os.path.relpath(fp, SRC), m.group(0)[:110]))
