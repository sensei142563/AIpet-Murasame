# -*- coding: utf-8 -*-
"""编译装机 → 关市场弹窗 → 启动 → 点「聊天」→ 读 files/diag.log（App 自己写的证据）。"""
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
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    print("编译失败，停止")
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("装机：" + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无)"])[-1][:120])


def adb(*a, timeout=180):
    rr = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=timeout)
    return (rr.stdout or "") + (rr.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:90]
    return "(未知)"


def tap_label(x, label):
    for m in re.finditer(r'<node[^>]*text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % label, x):
        cx = (int(m.group(1)) + int(m.group(3))) // 2
        cy = (int(m.group(2)) + int(m.group(4))) // 2
        adb("shell", "input", "tap", str(cx), str(cy))
        return cx, cy
    m2 = re.search(r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="%s"' % label, x)
    if m2:
        cx = (int(m2.group(1)) + int(m2.group(3))) // 2
        cy = (int(m2.group(2)) + int(m2.group(4))) // 2
        adb("shell", "input", "tap", str(cx), str(cy))
        return cx, cy
    return None


print("\n=== 关市场弹窗 ===")
xm = dump("mk3")
for lb in ("完成", "开启"):
    if tap_label(xm, lb):
        print("   点了「%s」" % lb)
        time.sleep(3)
        break
else:
    adb("shell", "am", "force-stop", "com.huawei.appmarket")
    time.sleep(2)
print("   前台:", fg())

print("\n=== 清空 diag.log 并启动 App ===")
adb("shell", "rm", "-f", EXT + "/diag.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
print("   前台:", fg())
x0 = dump("q1")
print("\n=== 点「聊天」 ===")
t = tap_label(x0, "聊天")
print("   点击坐标:", t)
time.sleep(6)
print("   点击后前台:", fg())

print("\n=== files/diag.log（App 自己写的）===")
log = adb("shell", "cat", EXT + "/diag.log")
print("\n".join("   " + l for l in (log or "(空/不存在)").splitlines()[-60:]))

print("\n=== 设备 logcat 里本 App 的异常 ===")
lc = adb("logcat", "-d", "-v", "brief")
bad = [l for l in lc.splitlines() if "AIpetDiag" in l or ("murasame" in l and re.search(r"FATAL|Exception", l))]
print("\n".join("   " + l[:170] for l in bad[-30:]) if bad else "   （无）")
