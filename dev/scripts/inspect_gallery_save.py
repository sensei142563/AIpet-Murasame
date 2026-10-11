# -*- coding: utf-8 -*-
"""① 查 manifest 权限与 min/targetSdk ② 打印当前 saveShot ③ 给出分区感知 + 通知相册的改写版。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MAN = os.path.join(CHAT, "app/src/main/AndroidManifest.xml")
AR = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt")

print("=== ① manifest 里的权限与 sdk ===")
s = io.open(MAN, encoding="utf-8", errors="replace").read()
for i, l in enumerate(s.splitlines(), 1):
    if re.search(r"(uses-permission|uses-sdk|minSdk|targetSdk|requestLegacyExternalStorage|"
                 r"android:requestLegacy|WRITE_EXTERNAL|READ_MEDIA|CAMERA)", l):
        print("   %5d| %s" % (i, l.strip()[:118]))

print()
print("=== ② gradle 里的 sdk 版本 ===")
for f in ("app/build.gradle.kts", "app/build.gradle", "build.gradle.kts", "build.gradle"):
    p = os.path.join(CHAT, f)
    if os.path.isfile(p):
        for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
            if re.search(r"(minSdk|targetSdk|compileSdk)", l):
                print("   %s:%d| %s" % (f, i, l.strip()[:110]))

print()
print("=== ③ 当前 saveShot / shoot 实现 ===")
a = io.open(AR, encoding="utf-8", errors="replace").read().splitlines()
for i, l in enumerate(a, 1):
    if re.search(r"(private fun shoot|private fun saveShot|MediaStore|RELATIVE_PATH|IS_PENDING|"
                 r"getExternalStoragePublicDirectory|scanFile|contentResolver|openOutputStream)", l):
        print("   %5d| %s" % (i, l.strip()[:118]))
