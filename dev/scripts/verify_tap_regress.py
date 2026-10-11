# -*- coding: utf-8 -*-
"""回归检查：快门改成 pointerInput 后，单点应只拍 1 张（长按拍 3 张已验证）。"""
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


def files():
    return re.findall(r"(AIpet_\d+_\d+\.png)", sh("ls", ARDIR))


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def bt(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(bt("聊天", dump("s0")))
time.sleep(5)
tap(bt("☰", dump("s1")))
time.sleep(3)
z = dump("s2")
tap(bt("⚙  设置", z) if bt("⚙  设置", z) else bt("设置", z))
time.sleep(3)
tap(bt("AR 模式（实景 + 桌宠）", dump("s3")))
time.sleep(12)

n0 = len(files())
print("① 单点快门 (612,2010) …（前 %d 张）" % n0)
sh("input", "tap", "612", "2010")
time.sleep(12)
n1 = len(files())
print("   单点后 %d 张 → 新增 %d 张（期望 1）" % (n1, n1 - n0))
print("   判定:", "✓ 单点=1 张，与长按区分正确" if n1 - n0 == 1 else "✗ 异常（%d 张）" % (n1 - n0))
p = os.path.join(TMP, "tap_regress.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
