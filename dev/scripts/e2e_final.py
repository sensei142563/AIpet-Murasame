# -*- coding: utf-8 -*-
"""正确版端到端：ASCII 输入 → 点 ↑ 发送 → 等回复 → 查 api/jev logcat → 查 F5 /infer。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
TMP = os.path.join(DEV, "shots")
APILOG = r"E:\university\order\python\pet\_audit_fish9269\_api_serve.log"
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"


def sh(*a, t=240):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def send_msg(txt):
    z = dump("s_in")
    m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
    if not m:
        print("   ✗ 无输入框")
        return False
    b = tuple(int(m.group(i)) for i in (1, 2, 3, 4))
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    time.sleep(1)
    sh("input", "text", txt)
    time.sleep(2)
    z = dump("s_typed")
    up = box("↑", z)
    print("   输入 %r；↑ 按钮位置 %s；框内 %s" % (txt, up, re.findall(r'text="([^"]*%s[^"]*)"' % txt, z)[:1]))
    if not up:
        print("   ✗ 找不到 ↑（可能被禁用或已变）")
        return False
    tap(up)
    time.sleep(3)
    return True


api0 = os.path.getsize(APILOG) if os.path.isfile(APILOG) else 0
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
print("起点 api=%d f5=%d" % (api0, f50))

sh("logcat", "-c")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("s0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("s1")))
time.sleep(6)

print("=== 发第一句（ASCII）===")
send_msg("hello there")

print("=== 等回复 / Jev（最多 110 秒）===")
hit = ""
for k in range(11):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            hit = new
            print("   ✓ api 日志出现 /jev/choose")
            break
    if k % 3 == 2:
        print("   %3ds 界面尾部: %s" % ((k + 1) * 10, texts(dump("s_w"))[-5:]))

print()
print("=== 手机端 JevClient 日志（logcat）===")
lg = sh("logcat", "-d", "-s", "JevClient:I", t=120)
print("\n".join(("   " + l.strip()[:134]) for l in (lg or "").splitlines()[-14:]) or "   （无）")

print()
print("=== F5（朗读已开 → 回复应自动念）===")
time.sleep(20)
if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
    new5 = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
    print("   含 /infer:", "/infer" in new5)
    if "/infer" in new5:
        print("\n".join(("      " + l.strip()[:124]) for l in new5.splitlines()[-6:]))
else:
    print("   F5 日志无新增 ✗")

print()
print("=== 判定 ===")
print("   手机 → 电脑 Jev:", "✓ 成立" if hit else "✗ 未触发")
p = os.path.join(TMP, "e2e_final.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
