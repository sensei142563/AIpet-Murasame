# -*- coding: utf-8 -*-
"""修底部导航被系统导航条盖住的问题：NavigationBar 显式使用 WindowInsets.navigationBars。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
F = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {'''
new = '''                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface,
                    // 真机实测（华为 MIS-AL00 / 1224x2776 / 540dpi）：
                    // enableEdgeToEdge + 透明导航栏 ⇒ 这个 NavigationBar 会一直画到屏幕最底，
                    // tab 的可点区（实测 y 2506~2776）与系统导航条重叠 ⇒
                    // 点「聊天」实际落到系统返回键 ⇒ App 被切走/退出（用户描述为"闪退"）。
                    // 显式指定 windowInsets 是**参数覆盖**（不会与默认值叠加），
                    // tab 会被抬到系统导航条之上。
                    windowInsets = WindowInsets.navigationBars
                ) {'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已给 NavigationBar 指定 windowInsets = WindowInsets.navigationBars")
else:
    print("✗ 锚点未命中")
    sys.exit(1)

print()
print("=== 编译 release ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:200])
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 安装到手机 ===")
adb = r"E:\Android\SDK\platform-tools\adb.exe"
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([adb, "-s", "4BD9K24C06021770", "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   " + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无输出)"])[-1][:140])
