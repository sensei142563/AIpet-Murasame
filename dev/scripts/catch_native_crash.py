# -*- coding: utf-8 -*-
"""流式抓完整 logcat → 点「聊天」复现 → 从完整日志里找原生崩溃（Fatal signal / backtrace）。"""
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
LIVE = os.path.join(SD, "live_logcat.txt")


def adb(*a, timeout=180):
    r = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:90]
    return "(未知)"


adb("shell", "logcat", "-b", "all", "-c")
fh = io.open(LIVE, "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([ADB, "-s", DEV, "logcat", "-b", "all", "-v", "threadtime"],
                        stdout=fh, stderr=subprocess.STDOUT)
time.sleep(2)

adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
print("启动后前台:", fg())

# 点「聊天」标签中心（diag.log 已证明这个坐标能触发 tab）
adb("shell", "input", "tap", "1112", "2695")
time.sleep(8)
print("点击后前台:", fg())

proc.terminate()
try:
    proc.wait(timeout=10)
except Exception:
    proc.kill()
fh.close()

txt = io.open(LIVE, encoding="utf-8", errors="replace").read()
print("\n=== 抓到的日志 %d 行 ===" % txt.count("\n"))

print("\n=== ① Fatal signal / backtrace / abort ===")
pats = re.compile(r"Fatal signal|backtrace:|signal \d+ \(SIG|Abort message|>>> com\.aipet|"
                  r"libc\s*:|DEBUG\s+:|art::|JNI DETECTED|CheckJNI")
hit = [l for l in txt.splitlines() if pats.search(l)]
if hit:
    for l in hit[:60]:
        print("   " + l.rstrip()[:175])
else:
    print("   （无）")

print("\n=== ② 本 App 的崩溃/异常相关行 ===")
hit2 = [l for l in txt.splitlines()
        if ("murasame" in l or "AIpetDiag" in l) and re.search(r"FATAL|Exception|Error|died|kill|signal|crash|abort", l, re.I)]
for l in hit2[-40:]:
    print("   " + l.rstrip()[:175])
if not hit2:
    print("   （无）")

print("\n=== ③ am_proc_died / am_kill / am_crash ===")
hit3 = [l for l in txt.splitlines() if re.search(r"am_proc_died|am_kill|am_crash|am_anr", l)]
for l in hit3[-15:]:
    print("   " + l.rstrip()[:175])
if not hit3:
    print("   （无）")

print("\n=== ④ 日志里 murasame 的最后 25 行（看崩溃前最后动作）===")
last = [l for l in txt.splitlines() if "murasame" in l]
for l in last[-25:]:
    print("   " + l.rstrip()[:175])
