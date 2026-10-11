# -*- coding: utf-8 -*-
"""验证缩略图：进 AR（占位）→ 拍照 → 缩略图出现 → 点击看大图（各留一张截图）。"""
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
PUB = "/sdcard/Pictures/AIpet/"


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


sh("rm", "-rf", PUB)
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("q0")))
time.sleep(5)
tap(box("☰", dump("q1")))
time.sleep(3)
z = dump("q2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
tap(box("AR 模式（实景 + 桌宠）", dump("q3")))
time.sleep(12)
z = dump("q4")
print("① 进 AR，界面文字:", texts(z)[:12])
print("   左下角占位「相册」:", box("相册", z) is not None)
shot("thumb_before.png")

sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
print("② 点快门 (%d,%d)" % (W // 2, H - 465))
sh("input", "tap", str(W // 2), str(H - 465))
for k in range(8):
    time.sleep(4)
    if "AIpet_" in sh("ls", PUB):
        print("   ✓ 第 %ds 相册已有照片" % ((k + 1) * 4))
        break
z = dump("q5")
print("   页面提示:", [t for t in texts(z) if ("已保存" in t or "失败" in t)][:2])
shot("thumb_after.png")

print("③ 点左下角缩略图（约 16dp, 底 26dp 处 → 像素约 (%d,%d)）" % (int(44 * 2.75), int(H - 80 * 2.75)))
# 缩略图：left padding 16dp + 56dp 中心 ≈ 44dp；bottom 26dp + 28dp ≈ 54dp
tx = int(44 * 2.75)
ty = H - int(54 * 2.75)
sh("input", "tap", str(tx), str(ty))
time.sleep(3)
z = dump("q6")
print("   点后文字（应出现「关闭」）:", [t for t in texts(z) if t in ("关闭", "图片读取失败")][:2])
shot("thumb_dialog.png")
print()
print("=== 判定 ===")
z6 = dump("q7")
print("   缩略图出现（不再是「相册」占位）:", box("相册", z6) is None)
print("   大图对话框出现（有「关闭」按钮）:", box("关闭", z6) is not None)
