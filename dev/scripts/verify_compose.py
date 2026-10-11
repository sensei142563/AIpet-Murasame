# -*- coding: utf-8 -*-
"""验证合成拍照：进 AR → 点快门 → 读提示 → pull 最新照片。"""
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
EXT = "/sdcard/Android/data/%s/files/ar/" % PKG


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


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("rm", "-rf", PUB)
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("c0")))
time.sleep(5)
tap(box("☰", dump("c1")))
time.sleep(3)
z = dump("c2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
tap(box("AR 模式（实景 + 桌宠）", dump("c3")))
time.sleep(12)
print("AR:", texts(dump("c4"))[:5])

sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
print("=== 点快门 (%d,%d) ===" % (W // 2, H - 465))
sh("input", "tap", str(W // 2), str(H - 465))
for k in range(8):
    time.sleep(4)
    z = dump("c5_%d" % k)
    msgs = [t for t in texts(z) if ("已保存" in t or "失败" in t or "拍摄" in t or "相册" in t)]
    if msgs:
        print("   提示:", msgs[:2])
    if "AIpet_" in sh("ls", PUB):
        print("   ✓ 公共目录已有照片（第 %ds）" % ((k + 1) * 4))
        break
print()
print("=== 公共目录 ===")
ls = sh("ls", "-l", PUB)
print(ls or "   （空）")
m2 = re.findall(r"(AIpet_\d+_\d+\.png)", ls)
if m2:
    name = m2[-1]
    dst = os.path.join(TMP, "composed_%s" % name)
    subprocess.run([ADB, "pull", PUB + name, dst], capture_output=True, timeout=180)
    print("   ✓ pull:", dst, os.path.getsize(dst) if os.path.exists(dst) else 0)
    print("   ★ 文件名（给下一步看图用）:", os.path.basename(dst))
else:
    print("   ✗ 没有照片")
p = os.path.join(TMP, "ar_compose_state.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
