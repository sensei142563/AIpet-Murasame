# -*- coding: utf-8 -*-
"""稳导航版验收：底部导航进设置 → AR 模式 → 拖桌宠 → 截图 + 拍照 → 拉成片（供看图比对位置是否一致）。"""
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


def tap(b, tag=""):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        print("   tap %s %s" % (tag, b))
        return True
    print("   ✗ 没找到 %s" % tag)
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def files():
    return re.findall(r"(AIpet_\d+_\d+\.png)", sh("ls", ARDIR))


def grab(name):
    p = os.path.join(TMP, name)
    with io.open(p, "wb") as f:
        q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
        f.write(q.stdout or b"")
    print("   截图:", p, os.path.getsize(p))
    return p


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(15)
# 底部导航：设置（以前验证过 x≈820,y≈2668）
sh("input", "tap", "820", "2668")
time.sleep(5)
z = dump("f1")
print("① 设置页文字（找 AR 入口）:", [t for t in texts(z) if "AR" in t][:3])
tap(box_any(["AR 模式（实景 + 桌宠）"], z), "AR模式")
time.sleep(15)
z = dump("f2")
tx = texts(z)
print("② AR 页:", tx[:12])
if not any("相册" in t for t in tx):
    print("   ✗ 没进 AR，放弃")
    sys.exit(1)
a = box_any(["相册"], z)
sy = ((a[1] + a[3]) // 2) if a else 2123
print("   相册框:", a, "→ 快门 y =", sy)
print()
print("③ 拖桌宠（右下方向）")
sh("input", "swipe", "480", "1250", "800", "1780", "1400")
time.sleep(4)
s1 = grab("wysiwyg_screen.png")
print()
print("④ 拍照")
n0 = files()
sh("input", "tap", "612", str(sy))
time.sleep(12)
n1 = files()
new = [f for f in n1 if f not in n0]
print("   新照片:", new)
if new:
    dst = os.path.join(TMP, "wysiwyg_photo_" + new[-1])
    subprocess.run([ADB, "pull", ARDIR + new[-1], dst], capture_output=True, timeout=300)
    print("   ✓ 成片已拉取:", dst, os.path.getsize(dst) if os.path.exists(dst) else 0)
    print()
    print("   请对照这两张：屏幕截图 %s  /  成片 %s" % (os.path.basename(s1), os.path.basename(dst)))
