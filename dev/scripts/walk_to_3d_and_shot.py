# -*- coding: utf-8 -*-
"""走到 3D 演示页并截图（每一步都截图 + 读日志），用眼睛看"为什么看不见"。"""
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
EXT = "/sdcard/Android/data/%s/files" % PKG


def adb(*a, timeout=240):
    r = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def shot(name):
    p = os.path.join(SD, "vrm_%s.png" % name)
    with io.open(p, "wb") as fh:
        r = subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                           stderr=subprocess.DEVNULL, timeout=240)
    return p if os.path.isfile(p) else None


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:80]
    return "(未知)"


def nodes(x):
    out = []
    for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x):
        at = (m.group("a1") or "") + (m.group("a2") or "")
        tm = re.search(r'text="([^"]*)"', at)
        out.append({"t": tm.group(1) if tm else "", "c": 'clickable="true"' in at,
                    "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                    "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
    return out


def tap_text(x, needle, wait=3.0):
    ns = nodes(x)
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
    return None


adb("shell", "rm", "-f", EXT + "/vrm.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
print("启动后前台:", fg())
print("  截图:", shot("1_home"))

print("\n点「聊天」:", tap_text(dump("s1"), "聊天", 4.0))
print("  前台:", fg(), " 截图:", shot("2_chat"))

print("\n点「☰」开抽屉:", tap_text(dump("s2"), "☰", 3.0))
x3 = dump("s3")
print("  抽屉里的文本:", [n["t"] for n in nodes(x3) if n["t"]][:14])

print("\n点「VRM 演示」:", tap_text(x3, "VRM 演示", 14.0))
print("  前台:", fg())
print("  截图:", shot("3_vrm"))

print("\n点「3D AR」:", tap_text(dump("s4"), "3D AR", 12.0))
print("  前台:", fg())
print("  截图:", shot("4_vrmar"))

print("\n=== vrm.log ===")
print("\n".join("   " + l for l in (adb("shell", "cat", EXT + "/vrm.log") or "(空)").splitlines()[-25:]))
print("\n=== vrm_ar.log ===")
print("\n".join("   " + l for l in (adb("shell", "cat", EXT + "/vrm_ar.log") or "(空)").splitlines()[-20:]))
