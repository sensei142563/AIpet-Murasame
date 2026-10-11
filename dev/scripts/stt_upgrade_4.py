# -*- coding: utf-8 -*-
"""聚焦验收：只点底部「设置」→ 找到「识别自检」并点击 → 读 live2d.log 对照真值。"""
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
    adb("shell", "input", "tap", str((bb[0] + bb[2]) // 2), str((bb[1] + bb[3]) // 2))
    print("   tap %s @(%d,%d)" % (tag, (bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2))
    time.sleep(2)


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
for attempt in range(4):
    z = dump("q%d" % attempt)
    b = box("设置", z)
    if b:
        tap(b, "底部导航 设置")
        break
    time.sleep(4)
# 等设置页渲染，最多 6 次 dump
found = None
for i in range(6):
    time.sleep(4)
    z = dump("w%d" % i)
    tx = texts(z)
    print("   [%d] 设置页文字: %s" % (i, [t for t in tx if len(t) < 18][:10]))
    if box("识别自检", z):
        found = box("识别自检", z)
        break
    if box("测试电脑语音", z):
        found = box("测试电脑语音", z)
        break
if not found:
    print("   ✗ 设置页里没找到自检按钮，dump 里含「自检/语音」的文本:",
          [t for t in texts(z) if "自检" in t or "语音" in t or "测试" in t][:8])
    sys.exit(1)
before = adb("shell", "tail", "-1", LOG).strip()
print("   点击前日志尾:", before[:110])
tap(found, "自检按钮")
time.sleep(25)
tail = adb("shell", "tail", "-4", LOG)
print("   点击后日志尾:")
for l in tail.splitlines():
    print("      " + l.strip()[:150])
m = re.search(r"selftest text=\[(.*?)\]", tail)
phone = m.group(1).strip() if m else ""
TRUTH = io.open(os.path.join(MAIN, "dev/scripts/_stt_truth.txt"), encoding="utf-8").read().strip()
print()
print("   真值      : %s" % TRUTH)
print("   手机新模型: %s" % (phone or "(没拿到)"))
if phone:
    import difflib
    print("   相似度    : %.2f" % difflib.SequenceMatcher(None, TRUTH, phone).ratio())
