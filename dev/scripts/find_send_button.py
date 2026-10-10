# -*- coding: utf-8 -*-
"""找聊天页输入行/发送按钮 → 给发送按钮加 contentDescription="发送" → 编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(CS, encoding="utf-8", errors="replace").read().splitlines()
print("=== 与发送/输入行相关的行 ===")
for i, l in enumerate(L, 1):
    if re.search(r"(send\(\)|BasicTextField|TextField|Icons\.(Default\.)?Send|contentDescription|IconButton|"
                 r"keyboardActions|imeAction|VoiceInput|麦克风|Mic)", l):
        print("   %5d| %s" % (i, l.strip()[:118]))
