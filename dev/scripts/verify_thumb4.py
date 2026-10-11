# -*- coding: utf-8 -*-
"""同会话内：拍照 → 点缩略图（截图量出的坐标 153,2338）→ 截图看是否弹出大图。"""
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


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box_text("聊天", dump("n0")))
time.sleep(5)
tap(box_text("☰", dump("n1")))
time.sleep(3)
z = dump("n2")
tap(box_text("⚙  设置", z) if box_text("⚙  设置", z) else box_text("设置", z))
time.sleep(3)
tap(box_text("AR 模式（实景 + 桌宠）", dump("n3")))
time.sleep(12)

sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
print("① 拍照 (%d,%d)" % (W // 2, H - 465))
sh("input", "tap", str(W // 2), str(H - 465))
for k in range(8):
    time.sleep(4)
    if "AIpet_" in sh("ls", "/sdcard/Pictures/AIpet/"):
        print("   ✓ 相册已有照片（%ds）" % ((k + 1) * 4))
        break
time.sleep(3)
print("   拍照后截图（缩略图应为照片）")
shot("thumb_state_now.png")

print("② 点缩略图 (153,2338)")
sh("input", "tap", "153", "2338")
time.sleep(4)
shot("thumb_tap_now.png")
z = dump("n4")
print("   界面文字:", [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()][:10])
print("   关闭按钮:", box_text("关闭", z))
