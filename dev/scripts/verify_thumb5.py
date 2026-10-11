# -*- coding: utf-8 -*-
"""按真实快门坐标(612,2140)拍照 → 比对 ar/ 最新时间戳确认新照片 → 缩略图 → 点它看大图。"""
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


def newest():
    ls = sh("ls", "-l", ARDIR)
    names = re.findall(r"(AIpet_\d+_\d+\.png)", ls)
    return names[-1] if names else None


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box_text(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def shot(name):
    p = os.path.join(TMP, name)
    with io.open(p, "wb") as f:
        q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
        f.write(q.stdout or b"")
    print("   截图:", p, os.path.getsize(p))
    return p


print("拍前最新:", newest())
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box_text("聊天", dump("w0")))
time.sleep(5)
tap(box_text("☰", dump("w1")))
time.sleep(3)
z = dump("w2")
tap(box_text("⚙  设置", z) if box_text("⚙  设置", z) else box_text("设置", z))
time.sleep(3)
tap(box_text("AR 模式（实景 + 桌宠）", dump("w3")))
time.sleep(12)
# 快门真实位置：从 zoom_after_5x.png 量出约 (700,2140)；取屏幕中心 x=612 的同一高度
for (sx, sy) in ((612, 2140), (700, 2140), (612, 2120), (612, 2160)):
    print("① 点快门 (%d,%d)" % (sx, sy))
    before = newest()
    sh("input", "tap", str(sx), str(sy))
    for k in range(6):
        time.sleep(3)
        now = newest()
        if now and now != before:
            print("   ✓ 有新照片:", now)
            break
    else:
        print("   ✗ 没有新照片（当前最新 %s）" % newest())
        continue
    break
time.sleep(3)
z = dump("w4")
print("② 缩略图仍是占位「相册」吗:", box_text("相册", z) is not None, "（False=成功 ✓）")
shot("thumb_ok.png")
print("③ 点缩略图 (153,2338)")
sh("input", "tap", "153", "2338")
time.sleep(4)
z = dump("w5")
close = box_text("关闭", z)
print("   出现「关闭」:", close)
shot("thumb_dialog_ok.png")
if close:
    tap(close)
    time.sleep(2)
    print("   关闭后消失:", box_text("关闭", dump("w6")) is None)
