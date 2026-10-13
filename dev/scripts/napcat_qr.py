# -*- coding: utf-8 -*-
"""把 NapCat 的登录二维码从 Termux 容器里取出来，放到手机相册，便于"小号 QQ 扫一扫"。

背景：二维码在容器内的 NapCat 目录下（qrcode.png）。容器在 Termux 私有目录里，
普通 adb 读不到；但我们发现 **run-as com.termux 可用** ⇒ 用 run-as 读出来，
再 push 到 /sdcard/Pictures/AIpet/（这个 adb 能写），手机相册就能看到、用小号扫。

用法：python dev/scripts/napcat_qr.py
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.termux"
HOME = "/data/data/com.termux/files/home"
ROOT = "/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/napcat"
OUT_DIR = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"


def adb(*args, timeout=600, binary=False):
    r = subprocess.run([ADB, "-s", DEV, *args], capture_output=True, timeout=timeout)
    if binary:
        return r.stdout
    return ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace")


def run_as(inner, timeout=600, binary=False):
    q = "'" + inner.replace("'", "'\\''") + "'"
    return adb("shell", "run-as", PKG, "sh", "-c", q, timeout=timeout, binary=binary)


print("=== ① 找二维码文件 ===")
found = run_as("find %s -maxdepth 8 -iname '*qrcode*' 2>/dev/null | head -5" % ROOT).strip()
print("   " + (found or "(没找到 qrcode 文件)"))
if not found:
    # 退一步：看看 NapCat 是否在跑、日志里有没有二维码链接
    print("   --- 容器 rootfs 是否存在 ---")
    print("   " + run_as("ls -d %s 2>&1" % ROOT).strip()[:200])
    print("   --- NapCat 目录 ---")
    print("   " + run_as("ls -d %s/root/Napcat 2>&1" % ROOT).strip()[:200])
    print("   --- 最近日志里跟二维码/链接有关的行 ---")
    lg = run_as("find %s/root -maxdepth 8 -name '*.log' 2>/dev/null | head -5" % ROOT).strip()
    for f in (lg or "").splitlines():
        print("   " + run_as("tail -40 '%s' 2>/dev/null | grep -iE 'qrcode|qr|扫码|登录' | tail -8" % f).strip()[:400])
    sys.exit(0)

path = found.splitlines()[0].strip()
print("   二维码：", path)
raw = run_as("cat '%s'" % path, binary=True)
print("   读到 %d 字节" % len(raw))
if len(raw) < 100:
    print("   ✗ 内容太小，可能不是 PNG")
    sys.exit(1)

local = os.path.join(OUT_DIR, "napcat_qr.png")
with io.open(local, "wb") as fh:
    fh.write(raw)
print("   已保存到电脑：", local)

print()
print("=== ② 推到手机相册（小号 QQ 可从相册取码）===")
subprocess.run([ADB, "-s", DEV, "shell", "mkdir", "-p", "/sdcard/Pictures/AIpet"],
               capture_output=True, timeout=120)
r = adb("push", local, "/sdcard/Pictures/AIpet/napcat_qr.png")
print("   " + r.strip()[-120:])
adb("shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
    "-d", "file:///sdcard/Pictures/AIpet/napcat_qr.png")
print("   ⇒ 手机相册 → Pictures/AIpet/napcat_qr.png，用小号 QQ「扫一扫 → 相册」选它")
