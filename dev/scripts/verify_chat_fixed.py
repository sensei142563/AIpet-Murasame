# -*- coding: utf-8 -*-
"""验证：进入聊天页后进程是否还活着（修复前必崩）。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG


def adb(*a, timeout=180):
    r = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:88]
    return "(未知)"


adb("shell", "rm", "-f", EXT + "/diag.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
print("启动后 pid=%s" % (adb("shell", "pidof", PKG).strip() or "(空)"))
print("   diag 尾部:", (adb("shell", "tail", "-n", "3", EXT + "/diag.log") or "").strip().replace("\n", " | "))

adb("shell", "input", "tap", "1112", "2695")     # 聊天 tab
print("\n已点「聊天」，连续观察 20 秒：")
alive_all = True
for i in range(4):
    time.sleep(5)
    p = adb("shell", "pidof", PKG).strip()
    if not p:
        alive_all = False
    print("   [%2ds] pid=%s" % ((i + 1) * 5, p or "**空 = 进程死了**"))

print("\n=== diag.log 全文 ===")
log = adb("shell", "cat", EXT + "/diag.log")
print("\n".join("   " + l for l in (log or "(空)").splitlines()[-40:]))

print("\n=== 结论 ===")
print("   进程存活 20 秒以上：%s" % ("✓ 修好了" if alive_all else "✗ 还会死"))
print("   当前前台：%s" % fg())
