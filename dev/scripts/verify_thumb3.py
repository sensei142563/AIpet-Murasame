# -*- coding: utf-8 -*-
"""用 content-desc="最近一张" 精确定位缩略图 → 点击 → 验证大图对话框（「关闭」出现）。"""
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


def boxes_text(label, xml):
    return [(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def boxes_desc(pat, xml):
    return [(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
            for m in re.finditer(r'content-desc="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % pat, xml)]


def box_text(label, xml):
    b = boxes_text(label, xml)
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


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box_text("聊天", dump("m0")))
time.sleep(5)
tap(box_text("☰", dump("m1")))
time.sleep(3)
z = dump("m2")
tap(box_text("⚙  设置", z) if box_text("⚙  设置", z) else box_text("设置", z))
time.sleep(3)
tap(box_text("AR 模式（实景 + 桌宠）", dump("m3")))
time.sleep(12)

sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
print("① 拍一张 (%d,%d)" % (W // 2, H - 465))
sh("input", "tap", str(W // 2), str(H - 465))
for k in range(8):
    time.sleep(4)
    if "AIpet_" in sh("ls", "/sdcard/Pictures/AIpet/"):
        print("   ✓ 相册已有照片")
        break
time.sleep(2)
z = dump("m4")
d = boxes_desc("最近一张", z)
print("② 缩略图（content-desc=最近一张）位置:", d)
if not d:
    print("   ✗ 找不到缩略图（可能还没生成）→ 打印所有 content-desc：")
    print("   ", re.findall(r'content-desc="([^"]+)"', z)[:12])
    sys.exit(1)
tap(d[0])
time.sleep(3)
z2 = dump("m5")
close = box_text("关闭", z2)
print("③ 点后是否出现「关闭」:", close, "；页面文字:", [t for t in re.findall(r'text="([^"]*)"', z2) if t.strip()][:8])
shot("thumb_dialog3.png")
if close:
    print("   ★★ 大图对话框验证成功 ✓")
    tap(close)
    time.sleep(2)
    z3 = dump("m6")
    print("④ 点关闭后「关闭」是否消失:", box_text("关闭", z3) is None)
    shot("thumb_dialog_closed.png")
else:
    print("   ✗ 仍未见「关闭」")
