# -*- coding: utf-8 -*-
"""跑 NetDiagTest（含新增的蜂窝用例）+ 编译装机 + 真机复验设置页那行文案。"""
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
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== ① 单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.NetDiagTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:190])
p = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.NetDiagTest.xml")
if os.path.isfile(p):
    x = io.open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   NetDiagTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,260})', x):
        print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:220]))

print()
print("=== ② 编译 + 装机 ===")
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                    cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=ENV, timeout=7200)
for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r2.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r3 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装机:", [l for l in ((r3.stdout or "") + (r3.stderr or "")).splitlines()
                   if "Success" in l or "Failure" in l][:1] or "?")


def adb(*a, timeout=300):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def tap(x, needle, wait=3.0, scroll=3):
    for _ in range(scroll):
        ns = []
        for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x):
            at = (m.group("a1") or "") + (m.group("a2") or "")
            tm = re.search(r'text="([^"]*)"', at)
            ns.append({"t": tm.group(1) if tm else "", "c": 'clickable="true"' in at,
                       "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                       "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
        for i, nd in enumerate(ns):
            if needle in nd["t"]:
                tx, ty = (nd["x1"] + nd["x2"]) // 2, (nd["y1"] + nd["y2"]) // 2
                tgt = None
                for j in range(i - 1, -1, -1):
                    c = ns[j]
                    if c["c"] and c["x1"] <= tx <= c["x2"] and c["y1"] <= ty <= c["y2"]:
                        tgt = c
                        break
                tgt = tgt or nd
                cx, cy = (tgt["x1"] + tgt["x2"]) // 2, (tgt["y1"] + tgt["y2"]) // 2
                adb("shell", "input", "tap", str(cx), str(cy))
                time.sleep(wait)
                return (cx, cy)
        adb("shell", "input", "swipe", "612", "1900", "612", "1000", "250")
        time.sleep(1.2)
        x = dump("nd2_sc")
    return None


print()
print("=== ③ 真机复验（设置页那行现在应该说明是移动数据）===")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
tap(dump("m1"), "聊天", 4.0)
tap(dump("m2"), "☰", 3.0)
tap(dump("m3"), "设置", 4.0)
tap(dump("m4"), "网络自检", 20.0)
x = dump("m5")
for m in re.finditer(r'text="([^"]{1,160})"', x):
    v = m.group(1)
    if any(k in v for k in ("本机", "移动数据", "热点", "找到电脑", "没扫到", "网络自检")):
        print("   " + v[:190])
