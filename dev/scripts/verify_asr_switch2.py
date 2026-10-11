# -*- coding: utf-8 -*-
"""用底部导航坐标进设置页（设置 = (862,2641)），截图验证新开关行。"""
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
PKG = "com.aipet.murasame"


def adb(*a, timeout=240):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:90]
    return "(未知)"


print("前台:", fg())
if PKG not in fg():
    adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
    time.sleep(10)
print("前台:", fg())
print("点底部「设置」(862,2641) …")
adb("shell", "input", "tap", "862", "2641")
time.sleep(4)
x = dump("t2")
vals = []
for m in re.finditer(r'text="([^"]{1,44})"', x):
    if m.group(1) and m.group(1) not in vals:
        vals.append(m.group(1))
print("页面文本：")
for v in vals[:30]:
    print("   " + v)
p = os.path.join(SD, "settings_asr_switch.png")
with io.open(p, "wb") as fh:
    subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                   stderr=subprocess.DEVNULL, timeout=240)
print("截图:", p)
print("出现新行「离线识别（实验）」：", "离线识别（实验）" in x)
