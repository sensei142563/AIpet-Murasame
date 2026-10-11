# -*- coding: utf-8 -*-
"""找出"聊天页会让 Activity 结束"的代码：全局未捕获异常处理器 / finish() / exitProcess / BackHandler。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

PATS = [
    (r"UncaughtExceptionHandler|setDefaultUncaughtExceptionHandler|uncaughtException", "全局异常处理器"),
    (r"exitProcess|System\.exit|killProcess", "强制退出进程"),
    (r"\.finish\(\)|finishAndRemoveTask", "结束 Activity"),
    (r"activity\?\.finish|actRef\?\.finish", "actRef.finish"),
]
for pat, label in PATS:
    print("=== %s（/%s/）===" % (label, pat))
    found = False
    for base, dirs, fs in os.walk(SRC):
        for f in fs:
            if not f.endswith(".kt"):
                continue
            p = os.path.join(base, f)
            for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
                if re.search(pat, l):
                    print("   %-34s %4d| %s" % (os.path.relpath(p, SRC), i, l.strip()[:120]))
                    found = True
    if not found:
        print("   （无）")
    print()

print("=== ChatScreen 里的 BackHandler / LaunchedEffect / 可能抛异常的地方 ===")
cs = os.path.join(SRC, "ui/ChatScreen.kt")
for i, l in enumerate(io.open(cs, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if re.search(r"BackHandler|LaunchedEffect|runCatching|throw |require\(|check\(|!!|error\(", l):
        print("   %5d| %s" % (i, l.strip()[:135]))
