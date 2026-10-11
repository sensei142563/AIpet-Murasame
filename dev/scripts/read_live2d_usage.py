# -*- coding: utf-8 -*-
"""读 ChatScreen 里 Live2D 视图的创建/销毁，以及 Live2D 视图类本身，定位"重复初始化 + 提前 Dispose"。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
CS = os.path.join(SRC, "ui/ChatScreen.kt")

lines = io.open(CS, encoding="utf-8", errors="replace").read().split("\n")
print("=== ChatScreen 里 Live2D 相关行 ===")
for i, l in enumerate(lines, 1):
    if re.search(r"[Ll]ive2[Dd]|JniBridge|Cubism|AndroidView|onDispose|remember\s*\{|modelDir", l):
        print("%5d| %s" % (i, l.rstrip()[:150]))

print()
print("=== 与 Live2D 视图/引擎有关的其他文件 ===")
for base, dirs, fs in os.walk(SRC):
    for f in fs:
        if f.endswith(".kt"):
            p = os.path.join(base, f)
            s = io.open(p, encoding="utf-8", errors="replace").read()
            if re.search(r"CubismFramework|JniBridgeJava|nativeInit|nativeDispose|Live2DView|Live2dView", s):
                print("   %-46s 命中 %d 处" % (os.path.relpath(p, SRC),
                      len(re.findall(r"CubismFramework|JniBridgeJava|nativeInit|nativeDispose|Live2DView|Live2dView", s))))
