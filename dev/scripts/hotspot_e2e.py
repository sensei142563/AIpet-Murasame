# -*- coding: utf-8 -*-
"""热点链路决定性验证：撤掉 USB 转发（只留热点）→ 聊天页发一句 → 看 api.log/f5tts.log 是否被调用。"""
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
USB = "4BD9K24C06021770"
NET = "192.168.43.1:5555"
LOGS = os.path.join(MAIN, "dev", "logs")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def adb(*a, t=300, dev=None):
    cmd = [ADB] + (["-s", dev] if dev else []) + list(a)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=t).stdout or ""


def size(name):
    p = os.path.join(LOGS, name)
    return os.path.getsize(p) if os.path.isfile(p) else 0


def tail(name, n=6):
    p = os.path.join(LOGS, name)
    if not os.path.isfile(p):
        return []
    return io.open(p, encoding="utf-8", errors="replace").read().splitlines()[-n:]


print("=== ① 只留热点通道：撤掉 USB 的转发 ===")
adb("reverse", "--remove-all", dev=USB)
print("   USB 通道转发:", adb("reverse", "--list", dev=USB).strip() or "(空 ✓)")
print("   热点通道转发:", adb("reverse", "--list", dev=NET).replace("\n", " | ").strip())
note("热点通道仍有两条转发", "28565" in adb("reverse", "--list", dev=NET) and "9881" in adb("reverse", "--list", dev=NET))

api_b, f5_b = size("api.log"), size("f5tts.log")
print("   日志基线: api=%d f5=%d" % (api_b, f5_b))

print()
print("=== ② 在聊天页发一句话（走 App → 127.0.0.1 → 热点 adb 反向 → 电脑）===")


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
    time.sleep(2.5)
    return True


adb("shell", "input", "keyevent", "KEYCODE_WAKEUP", dev=NET)
adb("shell", "am", "force-stop", PKG, dev=NET)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG, dev=NET)
time.sleep(16)
z = dump("n1")
tap(box("聊天", z), "底部导航 聊天")
time.sleep(6)
z = dump("n2")
tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
print("   聊天页:", tx[:6])
# 输入框：找 content-desc 或 hint 文本
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
if not m:
    m = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*class="android.widget.EditText"', z)
if m:
    b = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    tap(b, "输入框")
    time.sleep(1.5)
    adb("shell", "input", "text", "hello", dev=NET)
    time.sleep(1.5)
    z = dump("n3")
    sent = False
    for lb in ("↑", "发送", "Send"):
        if tap(box(lb, z), "发送 " + lb):
            sent = True
            break
    note("已发送一条消息", sent)
else:
    print("   ✗ 没找到输入框")
time.sleep(30)

print()
print("=== ③ 电脑端日志是否真的被调用（这就是热点链路的铁证）===")
api_a, f5_a = size("api.log"), size("f5tts.log")
print("   日志变化: api %d→%d   f5 %d→%d" % (api_b, api_a, f5_b, f5_a))
for l in tail("api.log", 5):
    print("   api | " + l.strip()[:140])
for l in tail("f5tts.log", 4):
    print("   f5  | " + l.strip()[:140])
note("电脑 api.py 收到了手机请求（api.log 增长）", api_a > api_b)
note("电脑 F5 参与了语音合成（f5tts.log 增长）", f5_a > f5_b)
print()
print("总结:", "★ 热点链路端到端打通 ✓" if (api_a > api_b) else "未观察到调用，需要再看")
