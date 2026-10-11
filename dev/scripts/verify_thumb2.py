# -*- coding: utf-8 -*-
"""复验：点左下角缩略图（正确坐标 ~150,2370）→ 看是否弹出大图（有「关闭」）。"""
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


def boxes(label, xml):
    return [(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def box(label, xml):
    b = boxes(label, xml)
    return b[0] if b else None


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


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("r0")))
time.sleep(5)
tap(box("☰", dump("r1")))
time.sleep(3)
z = dump("r2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
tap(box("AR 模式（实景 + 桌宠）", dump("r3")))
time.sleep(12)

# 先拍一张，保证有缩略图
sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
print("① 拍照 (%d,%d)" % (W // 2, H - 465))
sh("input", "tap", str(W // 2), str(H - 465))
for k in range(8):
    time.sleep(4)
    if "AIpet_" in sh("ls", "/sdcard/Pictures/AIpet/"):
        print("   ✓ 已有照片（%ds）" % ((k + 1) * 4))
        break
img = boxes("", dump("r4"))
print("   拍后占位「相册」还在吗:", box("相册", dump("r5")) is not None)

# 用截图找缩略图位置：直接按推算坐标点，再扫几个邻近点
print("② 点缩略图（多个候选坐标）")
for (tx, ty) in ((150, 2370), (150, 2340), (150, 2400), (120, 2370)):
    print("   试 (%d,%d)" % (tx, ty))
    sh("input", "tap", str(tx), str(ty))
    time.sleep(3)
    z = dump("r6_%d_%d" % (tx, ty))
    close = box("关闭", z)
    tx2 = [t for t in texts(z) if t in ("关闭", "图片读取失败")]
    print("      页面文字含关闭/失败:", tx2[:2], "；关闭按钮:", close)
    if close:
        print("   ★ 大图弹出了 ✓")
        break
shot("thumb_dialog2.png")
