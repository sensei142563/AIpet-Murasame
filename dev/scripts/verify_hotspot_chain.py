# -*- coding: utf-8 -*-
"""热点已通：① 双向连通测试 ② 从电脑测两个服务端口 ③ 手机上点「网络自检（找电脑）」看是否扫到并自动填地址。"""
import io
import os
import re
import socket
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
PC_IP = "192.168.43.237"
PHONE_HOTSPOT = "192.168.43.1"

print("=== ① 双向连通 ===")
for name, cmd in (("电脑 → 手机热点网关", ["ping", "-n", "2", "-w", "1500", PHONE_HOTSPOT]),):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    ok = "TTL=" in (r.stdout or "")
    print("   %-22s %s" % (name, "通 ✓" if ok else "不通 ✗"))

r = subprocess.run([ADB, "-s", DEV, "shell", "ping", "-c", "2", "-W", "2", PC_IP],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
print("   %-22s %s" % ("手机 → 电脑", "通 ✓" if "0% packet loss" in (r.stdout or "") or
                      "2 packets transmitted, 2 received" in (r.stdout or "") else
                      ("不通 ✗ " + (r.stdout or "").strip().splitlines()[-1][:60] if r.stdout else "?")))

print()
print("=== ② 电脑两个服务端口（手机要连的）===")
for p in (28565, 9881):
    try:
        with socket.create_connection((PC_IP, p), 2.0):
            print("   %s:%d  ✓ 可连" % (PC_IP, p))
    except Exception as e:
        print("   %s:%d  ✗ %s" % (PC_IP, p, e))

print()
print("=== ③ 手机 App：点「网络自检（找电脑）」===")


def adb(*a, timeout=300):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


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
        x = dump("hs_sc")
    return None


if PKG not in adb("shell", "dumpsys", "activity", "activities").split("mResumedActivity")[-1][:90]:
    adb("shell", "am", "force-stop", PKG)
    time.sleep(1)
    adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
    time.sleep(10)
tap(dump("q1"), "聊天", 4.0)
tap(dump("q2"), "☰", 3.0)
tap(dump("q3"), "设置", 4.0)
hit = tap(dump("q4"), "网络自检", 30.0)
print("   点了「网络自检」:", hit)
x = dump("q5")
for v in [m.group(1) for m in re.finditer(r'text="([^"]{1,220})"', x)]:
    if any(k in v for k in ("本机", "热点", "找到电脑", "没扫到", "移动数据", "网络很大", "自动填入")):
        print("   " + v[:240])

print()
print("=== ④ App 里现在保存的两个地址 ===")
for f in ("voice_base.txt", "jev_base.txt", "voice.json", "jev.json"):
    out = adb("shell", "cat", "/sdcard/Android/data/%s/files/%s" % (PKG, f))
    if out and "No such" not in out:
        print("   %s = %s" % (f, out.strip()[:90]))
ls = adb("shell", "ls", "/sdcard/Android/data/%s/files/" % PKG)
print("   （外部目录里与地址有关的文件：）")
for l in (ls or "").split():
    if any(k in l.lower() for k in ("voice", "jev", "base", "addr", "url")):
        print("      " + l)
