# -*- coding: utf-8 -*-
"""验证：点底部「聊天」后到底进不进聊天页（有了逻辑保险，结果应当可判定：聊天页 或 首页，不该回桌面）。"""
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


def adb(*a, timeout=180):
    r = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def fg():
    out = adb("shell", "dumpsys", "activity", "activities")
    for l in out.splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:110]
    return "(未知)"


def texts(x, n=22):
    v = []
    for m in re.finditer(r'text="([^"]{1,26})"', x):
        if m.group(1) and m.group(1) not in v:
            v.append(m.group(1))
    return v[:n]


adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
x0 = dump("v1")
print("启动后：")
print("   前台:", fg())
print("   文本:", " | ".join(texts(x0)))

# 找「聊天」文字节点 → 点它最近的 clickable 祖先中心
nodes = []
for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x0):
    attrs = (m.group("a1") or "") + (m.group("a2") or "")
    tm = re.search(r'text="([^"]*)"', attrs)
    nodes.append({"text": tm.group(1) if tm else "",
                  "click": 'clickable="true"' in attrs,
                  "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                  "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
target = None
for i, nd in enumerate(nodes):
    if nd["text"] == "聊天":
        tx, ty = (nd["x1"] + nd["x2"]) // 2, (nd["y1"] + nd["y2"]) // 2
        for j in range(i - 1, -1, -1):
            c = nodes[j]
            if c["click"] and c["x1"] <= tx <= c["x2"] and c["y1"] <= ty <= c["y2"]:
                target = c
                break
        if target is None:
            target = nd
        print("\n「聊天」文字节点 y %d~%d；点击目标 y %d~%d → 点 (%d,%d)"
              % (nd["y1"], nd["y2"], target["y1"], target["y2"],
                 (target["x1"] + target["x2"]) // 2, (target["y1"] + target["y2"]) // 2))
        break
if target is None:
    print("\n✗ dump 里没找到「聊天」")
    sys.exit(1)

adb("shell", "input", "tap", str((target["x1"] + target["x2"]) // 2),
    str((target["y1"] + target["y2"]) // 2))
time.sleep(5)
x1 = dump("v2")
print("\n点击后：")
print("   前台:", fg())
print("   文本:", " | ".join(texts(x1)))
chat_like = any(k in x1 for k in ("发送", "输入", "聊天记录", "表情", "SEND", "Message"))
print("\n判定：")
print("   是否仍在 App 内：%s" % ("是 ✓" if "murasame" in fg() else "否 ✗（说明退出/被切走）"))
print("   是否像聊天页   ：%s" % ("是 ✓（出现输入框/发送等）" if chat_like else "看不出（可能是首页）"))
print("   主线程有无异常 ：见下（logcat 过滤本应用）")
out = adb("logcat", "-d", "-v", "brief")
bad = [l for l in out.splitlines() if re.search(r"murasame", l) and re.search(r"FATAL|Exception|Error", l)]
print("   " + ("\n   ".join(bad[-8:]) if bad else "（无异常行）"))
