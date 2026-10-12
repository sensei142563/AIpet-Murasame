# -*- coding: utf-8 -*-
"""验证能否用 adb 驱动 Termux：启动 → 点击终端 → 输入命令 → 从 uiautomator dump 读回显。"""
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


def adb(*a, timeout=300):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def texts(x, limit=40):
    out = []
    for m in re.finditer(r'text="([^"]{1,300})"', x):
        v = m.group(1)
        if v and v not in out:
            out.append(v)
    return out[:limit]


print("=== ① 启动 Termux ===")
adb("shell", "am", "start", "-n", "com.termux/.HomeActivity")
time.sleep(9)
fg = [l.strip() for l in adb("shell", "dumpsys", "activity", "activities").splitlines() if "mResumedActivity" in l]
print("   前台:", fg[0][:80] if fg else "?")

x = dump("t1")
print("   界面文本：")
for v in texts(x, 12):
    print("      " + v[:150])

print()
print("=== ② 点击终端区域（屏幕中上部）===")
adb("shell", "input", "tap", "612", "1200")
time.sleep(2)

print("=== ③ 输入测试命令（echo NAPCAT_TEST_123）===")
# input text 里空格要用 %s
adb("shell", "input", "text", "echo%sNAPCAT_TEST_123")
time.sleep(1)
adb("shell", "input", "keyevent", "66")     # ENTER
time.sleep(4)
x2 = dump("t2")
print("   界面文本（输入后）：")
for v in texts(x2, 25):
    print("      " + v[:200])
print()
print("   看到 NAPCAT_TEST_123 回显：", "NAPCAT_TEST_123" in x2)
