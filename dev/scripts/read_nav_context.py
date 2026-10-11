# -*- coding: utf-8 -*-
"""读 MainActivity 底部导航上下文 + AndroidManifest/theme 的窗口设置，决定正确的 insets 修法。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")

print("=== MainActivity 190~245 行 ===")
lines = io.open(os.path.join(SRC, "MainActivity.kt"), encoding="utf-8", errors="replace").read().split("\n")
for i in range(189, min(245, len(lines))):
    print("%4d| %s" % (i + 1, lines[i].rstrip()[:150]))

print()
print("=== MainActivity 里与窗口/insets 有关的全部行 ===")
for i, l in enumerate(lines, 1):
    if re.search(r"enableEdgeToEdge|WindowInsets|systemBars|navigationBars|fitsSystemWindows|"
                 r"setDecorFitsSystemWindows|Scaffold|contentWindowInsets|WindowCompat|"
                 r"statusBarColor|navigationBarColor", l):
        print("%4d| %s" % (i, l.strip()[:140]))

print()
print("=== AndroidManifest 的 theme / 窗口相关 ===")
mf = os.path.join(CHAT, "app/src/main/AndroidManifest.xml")
if os.path.isfile(mf):
    for i, l in enumerate(io.open(mf, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"theme|Theme|windowSoftInputMode|activity", l):
            print("%4d| %s" % (i, l.strip()[:140]))

print()
print("=== themes.xml 里的窗口项 ===")
for base, dirs, fs in os.walk(os.path.join(CHAT, "app/src/main/res")):
    for f in fs:
        if f.startswith("themes") and f.endswith(".xml"):
            p = os.path.join(base, f)
            print("   %s:" % os.path.relpath(p, CHAT))
            for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
                if re.search(r"window|statusBar|navigationBar|fitsSystemWindows|edge", l, re.I):
                    print("      %4d| %s" % (i, l.strip()[:130]))
