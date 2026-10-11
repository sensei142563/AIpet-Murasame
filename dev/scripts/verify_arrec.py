# -*- coding: utf-8 -*-
"""复验 AR 录屏：点「AR录屏」→ 授权框点「允许」→ 录 8 秒 → 停止 → 查 AR_*.mp4 + ffprobe。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
ARDIR = "/sdcard/Android/data/%s/files/ar/" % PKG


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box_any(labels, xml):
    for lb in labels:
        m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(lb), xml)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def ars():
    return re.findall(r"(AR_\d+_\d+\.mp4)", sh("ls", ARDIR))


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box_any(["聊天"], dump("b0")))
time.sleep(5)
tap(box_any(["☰"], dump("b1")))
time.sleep(3)
z = dump("b2")
tap(box_any(["⚙  设置", "设置"], z))
time.sleep(3)
tap(box_any(["AR 模式（实景 + 桌宠）"], dump("b3")))
time.sleep(12)
z = dump("b4")
print("① AR录屏按钮:", box_any(["AR录屏"], z), "；录前:", ars())
tap(box_any(["AR录屏"], z))
time.sleep(5)
z = dump("b5")
print("② 授权框:", [t for t in texts(z) if "允许" in t or "禁止" in t][:3])
tap(box_any(["允许"], z))
time.sleep(6)
z = dump("b6")
print("③ 授权后提示:", [t for t in texts(z) if "录屏" in t or "失败" in t][:2])
time.sleep(8)
tap(box_any(["AR录屏"], dump("b7")))
time.sleep(8)
z = dump("b8")
print("④ 停止后提示:", [t for t in texts(z) if "已保存" in t or "失败" in t][:2])
v = ars()
print("⑤ ar/ 里 AR_*.mp4:", v)
if v:
    dst = os.path.join(TMP, "arrec_" + v[-1])
    subprocess.run([ADB, "pull", ARDIR + v[-1], dst], capture_output=True, timeout=300)
    print("   ✓ pull:", dst, os.path.getsize(dst) if os.path.exists(dst) else 0)
    ff = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_name,width,height,duration", "-of", "default=noprint_wrappers=1", dst],
                        capture_output=True, text=True, timeout=120)
    print("   ffprobe:", (ff.stdout or ff.stderr or "").replace("\n", " ")[:200])
p = os.path.join(TMP, "arrec_ok.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
