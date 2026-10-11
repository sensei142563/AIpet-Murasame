# -*- coding: utf-8 -*-
"""判决性实验：触发离线合成后等 90 秒，看它是"慢"还是"真卡死"；
同时检查界面是否还能响应（dump 能否正常返回 / 前台是否仍是本应用）。"""
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


def dump(name):
    t0 = time.time()
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    body = io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
    return body, time.time() - t0


def tap(x, needle, wait=2.5, scroll=3):
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
        x, _ = dump("sc")
    return None


def tts_lines():
    log = adb("shell", "cat", EXT + "/live2d.log")
    return [l.strip() for l in (log or "").splitlines() if "[tts]" in l]


print("=== 准备：清日志 → 启动 → 进设置 ===")
adb("shell", "sh", "-c", "rm -f %s/live2d.log" % EXT)
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
x, _ = dump("d1")
print("   点聊天:", tap(x, "聊天", 4.0))
x, _ = dump("d2")
print("   点☰:", tap(x, "☰", 3.0))
x, _ = dump("d3")
print("   点设置:", tap(x, "设置", 4.0))
x, _ = dump("d4")
print("   点一下测试:", tap(x, "点一下测试", 2.0))
print("   （已触发，开始计时）")

for sec in (15, 30, 45, 60, 90):
    time.sleep(15)
    ls = tts_lines()
    body, dt = dump("d_probe")
    resp = "响应正常" if dt < 6 else ("**dump 耗时 %.1fs ⇒ 界面很可能卡住**" % dt)
    print("   [%3ds] [tts] 最后一行=%s" % (sec, (ls[-1][:80] if ls else "(无)")))
    print("         dump %.1fs（%s）" % (dt, resp))
    if any("ready lang" in l or "samples=" in l or "failed" in l for l in ls):
        print("         ⇒ 有结果了，停止等待")
        break

print()
print("=== 最终 [tts] 全部行 ===")
for l in tts_lines():
    print("   " + l[:170])
