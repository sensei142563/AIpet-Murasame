# -*- coding: utf-8 -*-
"""推 step2 并在 Termux 里执行，轮询日志。复用驱动逻辑。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.termux"
NAME = sys.argv[1] if len(sys.argv) > 1 else "2"
SH = os.path.join(MAIN, "dev", "scripts", "termux_boot_step%s.sh" % NAME)
DEVID = "/sdcard/Download/napcat_step%s.sh" % NAME
LOG = "/sdcard/Download/napcat_boot%s.log" % NAME


def adb(*a, timeout=600):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


print("push:", (adb("push", SH, DEVID) or "").strip().splitlines()[-1][:100])
adb("shell", "rm", "-f", LOG)
adb("shell", "am", "start", "-n", PKG + "/.HomeActivity")
time.sleep(8)
adb("shell", "input", "tap", "612", "1200")
time.sleep(2)
adb("shell", "input", "text", ("bash " + DEVID).replace(" ", "%s"))
time.sleep(1)
adb("shell", "input", "keyevent", "66")
print("已在 Termux 执行: bash " + DEVID)
print()
done = "DONE-STEP%s" % NAME
last = ""
for i in range(40):                      # 最多 ~13 分钟
    time.sleep(20)
    body = adb("shell", "cat", LOG)
    if body and body != last:
        last = body
        tail = [l for l in body.splitlines() if l.strip()][-4:]
        print("   [%3ds] %s" % ((i + 1) * 20, " ／ ".join(l.strip()[:78] for l in tail)))
    if done in (body or ""):
        print("   ⇒ %s 完成" % done)
        break
print()
print("=== 日志尾部 ===")
body = adb("shell", "cat", LOG)
for l in (body or "").splitlines()[-35:]:
    print("   " + l.rstrip()[:180])
