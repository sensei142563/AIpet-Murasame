# -*- coding: utf-8 -*-
"""查启动点与 LogBus → 在启动处加载 Jev/Voice 地址 + 把 Jev 日志接进 LogBus → 编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== ① LogBus 定义与包名 ===")
logbus = None
for dp, ds, fs in os.walk(BASE):
    for f in fs:
        p = os.path.join(dp, f)
        if not f.endswith(".kt"):
            continue
        s = io.open(p, encoding="utf-8", errors="replace").read()
        if re.search(r"object LogBus", s):
            logbus = p
            pkg = re.search(r"^package\s+([\w\.]+)", s, re.M)
            print("   %s（package %s）" % (os.path.relpath(p, BASE), pkg.group(1) if pkg else "?"))
            for i, l in enumerate(s.splitlines(), 1):
                if re.search(r"(object LogBus|fun log)", l):
                    print("      %5d| %s" % (i, l.strip()[:110]))
print()
print("=== ② 启动点（MainActivity / Application）===")
starts = []
for dp, ds, fs in os.walk(BASE):
    for f in fs:
        if f.endswith(".kt") and re.search(r"(MainActivity|App\.kt|Application)", f):
            p = os.path.join(dp, f)
            starts.append(p)
            L = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
            print("--- %s ---" % os.path.relpath(p, BASE))
            for i, l in enumerate(L, 1):
                if re.search(r"(class \w+|onCreate|setContent|JevClient|VoiceClient|load\()", l):
                    print("      %5d| %s" % (i, l.strip()[:112]))
print()
print("=== ③ 现在哪里会 load 地址 ===")
for dp, ds, fs in os.walk(BASE):
    for f in fs:
        if not f.endswith(".kt"):
            continue
        p = os.path.join(dp, f)
        L = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        for i, l in enumerate(L, 1):
            if re.search(r"(JevClient\.load|VoiceClient\.load|JevClient\.save|VoiceClient\.save)", l):
                print("   %s:%d| %s" % (os.path.relpath(p, BASE), i, l.strip()[:110]))
