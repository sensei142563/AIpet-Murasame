# -*- coding: utf-8 -*-
"""把 step1 脚本推到手机，用 adb 在 Termux 里执行它，然后轮询 /sdcard/Download/napcat_boot.log。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
SH = os.path.join(MAIN, "dev", "scripts", "termux_boot_step1.sh")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
LOG = "/sdcard/Download/napcat_boot.log"
PKG = "com.termux"


def adb(*a, timeout=600):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def read_log():
    return adb("shell", "cat", LOG)


print("=== ① 授予 Termux 存储权限（免得弹窗打断）===")
for p in ("android.permission.READ_EXTERNAL_STORAGE", "android.permission.WRITE_EXTERNAL_STORAGE"):
    r = adb("shell", "pm", "grant", PKG, p)
    print("   grant %-42s %s" % (p.split(".")[-1], (r or "").strip()[:60] or "ok"))

print()
print("=== ② 推送 step1 脚本到手机 ===")
r = adb("push", SH, "/sdcard/Download/napcat_step1.sh")
print("   " + (r or "").strip().splitlines()[-1][:120])

print()
print("=== ③ 启动 Termux 并在终端里执行脚本 ===")
adb("shell", "rm", "-f", LOG)
adb("shell", "am", "start", "-n", PKG + "/.HomeActivity")
time.sleep(9)
adb("shell", "input", "tap", "612", "1200")       # 点终端区，确保有焦点
time.sleep(2)
cmd = "bash%s/sdcard/Download/napcat_step1.sh"
adb("shell", "input", "text", cmd.replace(" ", "%s"))
time.sleep(1)
adb("shell", "input", "keyevent", "66")           # ENTER
print("   已输入: bash /sdcard/Download/napcat_step1.sh")

print()
print("=== ④ 轮询日志（每 20 秒看一次，最多 8 分钟）===")
last = ""
for i in range(24):
    time.sleep(20)
    body = read_log()
    if body and body != last:
        last = body
        tail = [l for l in body.splitlines() if l.strip()][-6:]
        print("   [%3ds] %s" % ((i + 1) * 20, " ／ ".join(l.strip()[:70] for l in tail)))
    if "DONE-STEP1" in (body or ""):
        print("   ⇒ STEP1 完成")
        break
print()
print("=== ⑤ 完整日志 ===")
body = read_log()
if body and body.strip():
    for l in body.splitlines()[-60:]:
        print("   " + l.rstrip()[:170])
else:
    print("   （日志为空 —— 说明 Termux 里那条命令没跑起来，需要换成手动/别的注入方式）")
