# -*- coding: utf-8 -*-
"""立刻回退 MainActivity 的改动（windowInsets + bottom padding），重新编译装机。

用户明确：他没有导航栏、改回去、就是闪退。所以我的"系统导航条吃掉点击"判断是错的，
先恢复原状，再用完整 logcat（不只是 crash buffer）抓真正的闪退原因。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")


def sh(args, cwd=None, timeout=3600):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=ENV)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


print("=== 回退前：手机仓工作区状态 ===")
out, _ = sh(["git", "-C", CHAT, "status", "--porcelain"])
print("   " + (out.strip().replace("\n", "\n   ") or "(干净)"))

print()
print("=== 回退 MainActivity.kt 到已提交版本 ===")
out, rc = sh(["git", "-C", CHAT, "checkout", "--",
              "app/src/main/java/com/aipet/murasame/MainActivity.kt"])
print("   " + (out.strip() or "✓ 已回退"))
out, _ = sh(["git", "-C", CHAT, "status", "--porcelain"])
print("   回退后工作区：" + (out.strip().replace("\n", " | ") or "干净 ✓"))

print()
print("=== 确认两处改动都不在了 ===")
src = io.open(os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt"),
              encoding="utf-8", errors="replace").read()
for k in ("bottom = 48.dp", "windowInsets = WindowInsets.navigationBars", "navigationBars"):
    print("   %-42s %s" % (k, "仍在 ✗" if k in src else "已移除 ✓"))

print()
print("=== 编译 + 装机（恢复原样）===")
out, rc = sh([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"], cwd=CHAT, timeout=7200)
for l in out.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if rc != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
out2, _ = sh([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk])
print("   " + ((out2.strip().splitlines() or ["(无)"])[-1])[:120])

print()
print("=== 清空全部日志，准备抓真正的闪退 ===")
for b in ("main", "crash", "events", "system"):
    sh([ADB, "-s", DEV, "logcat", "-b", b, "-c"])
print("   ✓ main/crash/events/system 已清空")
