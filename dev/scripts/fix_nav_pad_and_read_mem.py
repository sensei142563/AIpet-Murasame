# -*- coding: utf-8 -*-
"""① 读 MemoryScreen 的按钮 UI 块（找竖排文字）  ② 底部导航加 48dp 底部内边距
   ③ 编译装机  ④ dump 验证 tab 是否抬到 y<2560。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
MEM = os.path.join(SRC, "ui/MemoryScreen.kt")
MA = os.path.join(SRC, "MainActivity.kt")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== MemoryScreen 里所有按钮/文字标签（找竖排的那句）===")
lines = io.open(MEM, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(lines, 1):
    if re.search(r'Text\(\s*"|Button\(|OutlinedButton\(|ActionChip|Row\(|Column\(|Modifier\.width', l):
        if re.search(r"互通|导入|导出|备份|包", l) or re.search(r'Text\(\s*"', l):
            print("%4d| %s" % (i, l.strip()[:140]))

print()
print("=== 底部导航：加 48dp 底部内边距（华为手势导航不报 inset，只能显式抬）===")
t = io.open(MA, encoding="utf-8").read().replace("\r\n", "\n")
if "bottom = 48.dp" in t:
    print("· 已有")
else:
    old = '''                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface,'''
    new = '''                NavigationBar(
                    // 华为（MIS-AL00，手势导航）实测：系统把 navigationBars inset 报成 0，
                    // 但屏幕底部约 216px 仍被系统手势区吞掉触摸 ⇒ tab 文字（y≈2695）点下去
                    // 会被系统当成返回 ⇒ App 退出（用户描述为"一到聊天页就闪退"）。
                    // 系统既然不报 inset，就只能显式把内容抬起来：48dp ≈ 144px。
                    modifier = Modifier.padding(bottom = 48.dp),
                    containerColor = MaterialTheme.colorScheme.surface,'''
    if old in t:
        t = t.replace(old, new, 1)
        if "import androidx.compose.foundation.layout.padding" not in t:
            t = t.replace("import androidx.compose.foundation.layout.WindowInsets",
                          "import androidx.compose.foundation.layout.WindowInsets\n"
                          "import androidx.compose.foundation.layout.padding", 1)
        if "import androidx.compose.ui.unit.dp" not in t:
            t = t.replace("import androidx.compose.foundation.layout.padding",
                          "import androidx.compose.foundation.layout.padding\n"
                          "import androidx.compose.ui.unit.dp", 1)
        io.open(MA, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已加 modifier = Modifier.padding(bottom = 48.dp) + import")
    else:
        print("✗ 锚点未命中")

print()
print("=== 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装机：" + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无)"])[-1][:120])

print()
print("=== 验证 tab 的新 y 范围 ===")
subprocess.run([ADB, "-s", DEV, "shell", "am", "force-stop", "com.aipet.murasame"], capture_output=True)
subprocess.run([ADB, "-s", DEV, "shell", "am", "start", "-n", "com.aipet.murasame/.MainActivity"],
               capture_output=True)
time.sleep(10)
subprocess.run([ADB, "-s", DEV, "shell", "uiautomator", "dump", "/sdcard/nf.xml"], capture_output=True, timeout=180)
subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/nf.xml", os.path.join(SD, "nf.xml")], capture_output=True, timeout=180)
x = io.open(os.path.join(SD, "nf.xml"), encoding="utf-8", errors="replace").read()
navs = []
for m in re.finditer(r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>', x):
    if 'clickable="true"' in m.group(0):
        x1, y1, x2, y2 = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        if y1 > 2000 and (y2 - y1) > 60:
            navs.append((x1, y1, x2, y2))
for n in navs:
    print("   tab 可点区 x %4d~%4d y %4d~%4d" % n)
ok = bool(navs) and all(n[3] <= 2620 for n in navs)
print("   判定：%s（期望 y2 ≤ ~2620，即抬离系统手势区）" % ("✓ 已抬起" if ok else "✗ 仍太低"))
