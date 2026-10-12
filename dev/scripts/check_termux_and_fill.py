# -*- coding: utf-8 -*-
"""① 查 Termux 是否已安装 ② 尝试驱动 App 的「网络自检（找电脑）」自动填地址 ③ 看 onebot_local.log 现状。"""
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


def adb(*a, timeout=300):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


print("=== ① Termux / 相关应用是否已安装 ===")
pkgs = adb("shell", "pm", "list", "packages")
for key, name in (("com.termux", "Termux"), ("com.termux.api", "Termux:API"),
                  ("com.termux.boot", "Termux:Boot"), ("com.termux.widget", "Termux:Widget")):
    print("   %-14s %s" % (name, "已装 ✓" if key in (pkgs or "") else "未装 ✗"))
print("   已装的第三方包（含 termux/napcat/qq 关键字）：")
for l in (pkgs or "").splitlines():
    low = l.lower()
    if any(k in low for k in ("termux", "napcat", "onebot", "qq")):
        print("      " + l.strip())


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def fg():
    tail = adb("shell", "dumpsys", "activity", "activities")
    for l in tail.splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:80]
    return "(未知)"


def tap(x, needle, wait=3.0, scroll=4):
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
        x = dump("tm_sc")
    return None


print()
print("=== ② 当前前台 ===")
print("   " + fg())

print()
print("=== ③ 尝试：拉起 App → 聊天 → ☰ → 设置 → 网络自检 ===")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(11)
print("   点聊天:", tap(dump("z1"), "聊天", 4.0))
print("   点☰:", tap(dump("z2"), "☰", 3.0))
print("   点设置:", tap(dump("z3"), "设置", 4.0))
r = tap(dump("z4"), "网络自检", 30.0)
print("   点网络自检:", r)
x = dump("z5")
found = [m.group(1) for m in re.finditer(r'text="([^"]{1,220})"', x)
         if any(k in m.group(1) for k in ("本机", "找到电脑", "没扫到", "自动填入", "热点", "移动数据"))]
for v in found:
    print("   → " + v[:230])
if not found:
    print("   （没读到结果行；设置页文本样本：）")
    for v in [m.group(1) for m in re.finditer(r'text="([^"]{1,30})"', x)][:14]:
        print("      " + v)

print()
print("=== ④ onebot_local.log 最后 10 行（NapCat 客户端状态）===")
lg = adb("shell", "cat", EXT + "/onebot_local.log")
for l in (lg or "").splitlines()[-10:]:
    print("   " + l.strip()[:150])
