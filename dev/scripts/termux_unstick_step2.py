# -*- coding: utf-8 -*-
"""step2 卡在 apt 的 sources.list 配置询问 —— 反复回车（默认 N=保留现有）把它推过去，并继续监控。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
LOG = "/sdcard/Download/napcat_boot2.log"


def adb(*a, timeout=600):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


last = ""
for i in range(40):
    body = adb("shell", "cat", LOG)
    tail = [l for l in (body or "").splitlines() if l.strip()][-3:]
    # 若看到询问字样，就回车
    if body and ("[default=N] ?" in body.splitlines()[-3:][-1] if body.splitlines() else False):
        pass
    recent = "\n".join((body or "").splitlines()[-6:])
    if "[default=N] ?" in recent or "[Y/n]" in recent or "(Y/I/N/O/D/Z)" in recent:
        adb("shell", "input", "keyevent", "66")     # ENTER = 默认 N
        print("   [%3ds] 检测到询问 ⇒ 已回车(默认 N)" % ((i + 1) * 12))
    if body != last:
        last = body
        print("   [%3ds] %s" % ((i + 1) * 12, " ／ ".join(l.strip()[:72] for l in tail)))
    if "DONE-STEP2" in (body or ""):
        print("   ⇒ STEP2 完成")
        break
    time.sleep(12)

print()
print("=== 日志尾部 40 行 ===")
body = adb("shell", "cat", LOG)
for l in (body or "").splitlines()[-40:]:
    print("   " + l.rstrip()[:180])
