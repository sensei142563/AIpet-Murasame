# -*- coding: utf-8 -*-
"""① 看电脑自己的 IP 与 api.py(28565) 是否在监听 ② 到手机上点「网络自检（找电脑）」并读结果。"""
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

print("=== ① 电脑侧 ===")
try:
    host = socket.gethostname()
    print("   主机名:", host)
    for info in socket.getaddrinfo(host, None, socket.AF_INET):
        ip = info[4][0]
        if not ip.startswith("127."):
            print("   本机 IPv4:", ip)
except Exception as e:
    print("   取 IP 失败:", e)


def port_open(h, p, t=0.5):
    try:
        with socket.create_connection((h, p), t):
            return True
    except Exception:
        return False


for p in (28565, 9881):
    print("   port %d 监听中: %s" % (p, port_open("127.0.0.1", p)))

print()
print("=== ② 手机侧：进设置 → 点「网络自检（找电脑）」===")


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
        x = dump("nd_sc")
    return None


adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
print("   点聊天:", tap(dump("n1"), "聊天", 4.0))
print("   点☰:", tap(dump("n2"), "☰", 3.0))
print("   点设置:", tap(dump("n3"), "设置", 4.0))
print("   点网络自检:", tap(dump("n4"), "网络自检", 25.0))
x = dump("n5")
vals = [m.group(1) for m in re.finditer(r'text="([^"]{1,120})"', x)]
print()
print("=== 设置页里与网络有关的文本 ===")
for v in vals:
    if any(k in v for k in ("本机", "热点", "找到电脑", "没扫到", "扫", "网络自检", "电脑地址")):
        print("   " + v[:170])
