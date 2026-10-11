# -*- coding: utf-8 -*-
"""补 WindowInsets.navigationBars 的 import → 编译 → 装机 → 用 dump 验证 tab 是否被抬离系统导航条。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
F = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")
need = "import androidx.compose.foundation.layout.navigationBars"
if need not in t:
    t = t.replace("import androidx.compose.foundation.layout.WindowInsets",
                  "import androidx.compose.foundation.layout.WindowInsets\n" + need, 1)
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 补 import androidx.compose.foundation.layout.navigationBars")
else:
    print("· import 已存在")

print()
print("=== 编译 release ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 安装 ===")
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   " + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无)"])[-1][:140])

print()
print("=== 验证：tab 的 y 范围是否被抬到系统导航条之上 ===")


def dump(name):
    subprocess.run([ADB, "-s", DEV, "shell", "uiautomator", "dump", "/sdcard/%s.xml" % name],
                   capture_output=True, timeout=180)
    subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name)],
                   capture_output=True, timeout=180)
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


subprocess.run([ADB, "-s", DEV, "shell", "am", "force-stop", "com.aipet.murasame"], capture_output=True)
subprocess.run([ADB, "-s", DEV, "shell", "am", "start", "-n", "com.aipet.murasame/.MainActivity"],
               capture_output=True)
import time
time.sleep(10)
x = dump("nav_fixed")
print("   dump %d 字节" % len(x))
navs = []
for m in re.finditer(r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>', x):
    if 'clickable="true"' in m.group(0):
        x1, y1, x2, y2 = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        if y1 > 2000 and (y2 - y1) > 60:
            navs.append((x1, y1, x2, y2))
print("   底部可点区域（y1>2000）：")
for n in navs:
    print("      x %4d~%4d  y %4d~%4d  中心=(%d,%d)" % (n[0], n[2], n[1], n[3],
                                                     (n[0] + n[2]) // 2, (n[1] + n[3]) // 2))
print("   屏幕高 2776；系统导航条从约 2560 开始 ⇒ 期望：tab 的 y2 ≤ ~2560")
ok = bool(navs) and all(n[3] <= 2600 for n in navs)
print("   判定：%s" % ("✓ tab 已被抬离系统导航条" if ok else "✗ 仍然延伸到系统导航区"))
