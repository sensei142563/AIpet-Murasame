# -*- coding: utf-8 -*-
"""在设置页向下滚动，找到「离线识别（实验）」并截图。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"


def adb(*a, timeout=240):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


found = False
for i in range(6):
    adb("shell", "input", "swipe", "612", "2000", "612", "900", "300")
    time.sleep(1.5)
    x = dump("u%d" % i)
    if "离线识别（实验）" in x:
        found = True
        print("✓ 第 %d 次滚动后找到「离线识别（实验）」" % (i + 1))
        vals = []
        for m in re.finditer(r'text="([^"]{1,40})"', x):
            if m.group(1) and m.group(1) not in vals:
                vals.append(m.group(1))
        print("   当前页面文本：")
        for v in vals[:16]:
            print("      " + v)
        p = os.path.join(SD, "settings_asr_switch.png")
        with io.open(p, "wb") as fh:
            subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                           stderr=subprocess.DEVNULL, timeout=240)
        print("   截图:", p)
        break
if not found:
    print("✗ 滚动 6 次仍未找到（可能需要更多滚动，或该行未编译进去）")
    print("   最后看到的文本：", [m.group(1) for m in re.finditer(r'text="([^"]{1,24})"', x)][:16])
