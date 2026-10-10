# -*- coding: utf-8 -*-
"""全仓搜所有语音/TTS 调用点，找出真正在念的那一处。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame"
PAT = re.compile(r"(TextToSpeech|\btts\b|\.speak\(|Speaker|say\(|OfflineTts|readAloud|朗读|utterance|"
                 r"VoiceClient|synthesize|MediaPlayer|playAudio)", re.I)

for dp, ds, fs in os.walk(BASE):
    for f in sorted(fs):
        if not f.endswith(".kt"):
            continue
        p = os.path.join(dp, f)
        L = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        hits = [(i, l) for i, l in enumerate(L, 1) if PAT.search(l)]
        if not hits:
            continue
        print("--- %s ---" % os.path.relpath(p, BASE))
        for i, l in hits[:30]:
            print("   %5d| %s" % (i, l.strip()[:118]))
