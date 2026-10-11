# -*- coding: utf-8 -*-
"""进设置页截图 + 文本确认新开关行出现。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"


def adb(*a, timeout=240):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def tap_text(x, needle, wait=3.0):
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
                cc = ns[j]
                if cc["c"] and cc["x1"] <= tx <= cc["x2"] and cc["y1"] <= ty <= cc["y2"]:
                    tgt = cc
                    break
            tgt = tgt or nd
            cx, cy = (tgt["x1"] + tgt["x2"]) // 2, (tgt["y1"] + tgt["y2"]) // 2
            adb("shell", "input", "tap", str(cx), str(cy))
            time.sleep(wait)
            return (cx, cy)
    return None


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:90]
    return "(未知)"


print("当前前台:", fg())
if PKG not in fg():
    adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
    time.sleep(9)
print("点底部「设置」:", tap_text(dump("s1"), "设置", 4.0))
x = dump("s2")
vals = []
for m in re.finditer(r'text="([^"]{1,40})"', x):
    if m.group(1) and m.group(1) not in vals:
        vals.append(m.group(1))
print("设置页文本：")
for v in vals[:26]:
    print("   " + v)
p = os.path.join(SD, "settings_asr_switch.png")
with io.open(p, "wb") as fh:
    subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                   stderr=subprocess.DEVNULL, timeout=240)
print("截图:", p)
print("是否出现新行：", "离线识别（实验）" in x)
