# -*- coding: utf-8 -*-
"""重建热点通道的两条转发（上次 --remove-all 是设备级，把两条都清了）→ 再发一条消息 → 看电脑日志。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = os.path.join(MAIN, "dev/shots")
NET = "192.168.43.1:5555"
LOGS = os.path.join(MAIN, "dev", "logs")


def adb(*a, t=300, dev=None):
    cmd = [ADB] + (["-s", dev] if dev else []) + list(a)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=t).stdout or ""


def size(n):
    p = os.path.join(LOGS, n)
    return os.path.getsize(p) if os.path.isfile(p) else 0


def tail(n, k=5):
    p = os.path.join(LOGS, n)
    return io.open(p, encoding="utf-8", errors="replace").read().splitlines()[-k:] if os.path.isfile(p) else []


print("=== ① 重建热点通道的两条转发 ===")
for p in (28565, 9881):
    adb("reverse", "tcp:%d" % p, "tcp:%d" % p, dev=NET)
lst = adb("reverse", "--list", dev=NET)
print("   转发列表:", lst.replace("\n", " | ").strip())
print("   通过全设备视角:", adb("reverse", "--list").replace("\n", " | ").strip())

print()
print("=== ② 验证手机侧监听是否真的存在（转发生效的直接证据）===")
stat = adb("shell", "cat /proc/net/tcp", dev=NET)
# 28565 = 0x6F95, 9881 = 0x2699（小端十六进制）
for port, hexp in ((28565, "6F95"), (9881, "2699")):
    hit = [l for l in stat.splitlines() if hexp in l.upper() and "0A" in l]
    print("   手机 /proc/net/tcp 含 %d (%s): %s" % (port, hexp, "✓ 有监听" if hit else "✗ 没看到"))

api_b, f5_b = size("api.log"), size("f5tts.log")
print()
print("=== ③ 再发一条消息 ===")


def dump(tag):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % tag, dev=NET)
    subprocess.run([ADB, "-s", NET, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=90)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


def tap(b, tag=""):
    if not b:
        print("   ✗ 没找到 %s" % tag)
        return False
    adb("shell", "input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2), dev=NET)
    print("   tap %s" % tag)
    time.sleep(2)
    return True


adb("shell", "input", "keyevent", "KEYCODE_WAKEUP", dev=NET)
adb("shell", "am", "force-stop", PKG, dev=NET)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG, dev=NET)
time.sleep(15)
z = dump("p1")
tap(box("聊天", z), "聊天")
time.sleep(5)
z = dump("p2")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
if m:
    tap((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))), "输入框")
    time.sleep(1.5)
    adb("shell", "input", "text", "hello again", dev=NET)
    time.sleep(1.5)
    z = dump("p3")
    for lb in ("↑", "发送"):
        if tap(box(lb, z), "发送 " + lb):
            break
else:
    print("   ✗ 输入框没找到")
time.sleep(35)

print()
print("=== ④ 电脑日志变化 ===")
api_a, f5_a = size("api.log"), size("f5tts.log")
print("   api %d→%d    f5 %d→%d" % (api_b, api_a, f5_b, f5_a))
for l in tail("api.log", 6):
    print("   api | " + l.strip()[:140])
for l in tail("f5tts.log", 5):
    print("   f5  | " + l.strip()[:140])
verdict = "★ 热点链路端到端打通 ✓（手机请求真的到电脑了）" if api_a > api_b else "仍未看到调用"
print()
print("总结:", verdict)
