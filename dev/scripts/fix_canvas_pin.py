# -*- coding: utf-8 -*-
"""修 3D 看不见的根因：body 高度 0 ⇒ canvas 永远不可见。
   把 canvas 直接钉在视口上（position:fixed + 100vw/100vh），不再依赖 body 高度。"""
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
IDX = os.path.join(CHAT, "app/src/main/assets/vrm/index.html")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(IDX, encoding="utf-8").read().replace("\r\n", "\n")

# 在 <style> 里补 canvas 规则
if "canvas{" not in t:
    t = t.replace("#tag{",
                  '''/* 【关键修复】canvas 必须自己钉在视口上。
   真机实测（2026-10-11）：body 的 clientHeight 竟然是 0（子元素几乎都是 position:fixed），
   于是 canvas 虽然在渲染（75 帧/秒）、尺寸也对，却**因为容器零高度而完全看不见** ——
   表现就是"3D 形象怎么都不出来"，而日志里一切正常。 */
canvas{position:fixed;left:0;top:0;width:100vw;height:100vh;display:block;z-index:0}
#tag{''', 1)
    print("✓ 已加 canvas 定位规则（position:fixed + 100vw/100vh）")
else:
    print("· 已有 canvas 规则")

io.open(IDX, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")


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


adb("shell", "rm", "-f", EXT + "/vrm.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
tap_text(dump("v1"), "聊天", 4.0)
tap_text(dump("v2"), "☰", 3.0)
tap_text(dump("v3"), "VRM 演示", 16.0)
p = os.path.join(SD, "vrm_10_canvasfix.png")
with io.open(p, "wb") as fh:
    subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                   stderr=subprocess.DEVNULL, timeout=240)
print("截图:", p)
log = adb("shell", "cat", EXT + "/vrm.log")
for l in (log or "").splitlines():
    if "title=P:" in l:
        print("P 行:", l.strip()[:220])
        break
