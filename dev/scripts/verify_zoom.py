# -*- coding: utf-8 -*-
"""验证变焦档位：点 2× → 顶栏读数应变 2.0×（顺带试 5×）。"""
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


def zoom_text(xml):
    for t in re.findall(r'text="([^"]*)"', xml):
        if re.match(r"^\d+\.\d×$", t.strip()):
            return t.strip()
    return None


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
tap(box("聊天", dump("k0")))
time.sleep(5)
tap(box("☰", dump("k1")))
time.sleep(3)
z = dump("k2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
tap(box("AR 模式（实景 + 桌宠）", dump("k3")))
time.sleep(12)
z = dump("k4")
print("① 初始读数:", zoom_text(z))
shot("zoom_1x.png")
for lbl in ("2×", "5×", "1×"):
    b = box(lbl, dump("k5_%s" % lbl))
    print("② 点 %s %s" % (lbl, b))
    tap(b)
    time.sleep(4)
    z = dump("k6_%s" % lbl)
    print("   → 读数:", zoom_text(z))
    shot("zoom_after_%s.png" % lbl.replace("×", "x"))
