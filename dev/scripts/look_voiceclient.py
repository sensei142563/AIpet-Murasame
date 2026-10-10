# -*- coding: utf-8 -*-
"""给 VoiceClient 加可取证日志（外部文件 + LogBus + logcat，每个失败点都记原因）→ 编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== VoiceClient.kt 现状（关键行）===")
s = io.open(VC, encoding="utf-8", errors="replace").read()
for i, l in enumerate(s.splitlines(), 1):
    if re.search(r"(fun speak|baseUrl|isSuccessful|return false|true$|MediaPlayer|File\(|cacheDir|"
                 r"RIFF|readTimeout|connectTimeout)", l):
        print("   %5d| %s" % (i, l.strip()[:118]))
