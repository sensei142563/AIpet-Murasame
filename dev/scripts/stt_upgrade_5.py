# -*- coding: utf-8 -*-
"""按正确路径（聊天 → ☰ → 设置）点「识别自检」，读 live2d.log 与真值/电脑结果对照。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
DEV = "4BD9K24C06021770"
TMP = os.path.join(MAIN, "dev", "shots")
LOG = "/sdcard/Android/data/%s/files/live2d.log" % PKG


def adb(*a, t=300):
    return subprocess.run([ADB, "-s", DEV] + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


def dump(tag):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=90)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


def tap(bb, tag=""):
    if not bb:
        print("   ✗ 没找到 %s" % tag)
        return False
    adb("shell", "input", "tap", str((bb[0] + bb[2]) // 2), str((bb[1] + bb[3]) // 2))
    print("   tap %s" % tag)
    time.sleep(2.5)
    return True


def find(labels, tries=6, wait=4):
    for i in range(tries):
        z = dump("d%d_%d" % (int(time.time()) % 1000, i))
        for lb in labels:
            b = box(lb, z)
            if b:
                return lb, b, z
        time.sleep(wait)
    return None, None, z


adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
lb, b, z = find(["聊天"])
tap(b, "聊天")
time.sleep(6)
lb, b, z = find(["☰"])
tap(b, "☰ 抽屉")
time.sleep(4)
lb, b, z = find(["⚙  设置", "设置"])
tap(b, "抽屉里的设置")
time.sleep(5)
lb, b, z = find(["识别自检", "测试电脑语音"], tries=6)
print("   目标:", lb)
if lb == "测试电脑语音":
    lb2, b2, z2 = find(["识别自检"], tries=3, wait=3)
    if lb2:
        lb, b = lb2, b2
before = adb("shell", "tail", "-1", LOG).strip()
print("   点击前:", before[:110])
tap(b, "点 " + str(lb))
time.sleep(25)
tail = adb("shell", "tail", "-4", LOG)
print("   点击后日志:")
for l in tail.splitlines():
    print("      " + l.strip()[:150])
m = re.search(r"selftest text=\[(.*?)\]", tail)
phone = m.group(1).strip() if m else ""
TRUTH = io.open(os.path.join(MAIN, "dev/scripts/_stt_truth.txt"), encoding="utf-8").read().strip()
print()
print("   真值      : %s" % TRUTH)
print("   手机新模型: %s" % (phone or "(没拿到)"))
if phone and phone != before:
    import difflib
    print("   相似度    : %.2f" % difflib.SequenceMatcher(None, TRUTH, phone).ratio())
