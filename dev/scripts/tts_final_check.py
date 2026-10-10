# -*- coding: utf-8 -*-
"""TTS 收尾：确保「朗读」=开 → 发一句 → pull voice.log 判定。"""
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
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
VOICELOG = "/sdcard/Android/data/com.aipet.murasame/files/voice.log"


def sh(*a, t=300):
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


def boxes(label, xml):
    return [tuple(int(m.group(i)) for i in (1, 2, 3, 4))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def box(label, xml):
    b = boxes(label, xml)
    return b[0] if b else None


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("v0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("v1")))
time.sleep(5)
tap(box("☰", dump("v2")))
time.sleep(3)
z = dump("v3")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
z = dump("v4")
print("=== 设置页语音区 ===")
row = None
for i, m in enumerate(re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)):
    t = m.group(1)
    if t.strip() in ("朗读", "开", "关", "朗读音色", "语音服务地址"):
        print("   %-10s @ (%s,%s)-(%s,%s)" % (t, m.group(2), m.group(3), m.group(4), m.group(5)))
# 找「朗读」这一行的「开/关」状态：同一横带的文本
m = re.search(r'text="朗读"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
state = None
if m:
    y1, y2 = int(m.group(2)), int(m.group(4))
    for mm in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z):
        yy1, yy2 = int(mm.group(2)), int(mm.group(4))
        if abs((yy1 + yy2) // 2 - (y1 + y2) // 2) < 60 and mm.group(1) in ("开", "关"):
            state = mm.group(1)
            row = (int(mm.group(2)), int(mm.group(3)), int(mm.group(4)), int(mm.group(5)))
print("   朗读当前状态:", state)
if state == "关" and row:
    tap(row)
    time.sleep(2)
    z = dump("v5")
    print("   已点开关 → 现在:", [t for t in texts(z) if t in ("开", "关")][:2])
elif state is None:
    print("   ⚠ 没读出状态（可能页面结构不同）")

# 顺手确认语音服务地址仍在
print("   语音服务地址显示:", [t for t in texts(dump("v6")) if "127.0.0.1" in t])
sh("rm", "-f", VOICELOG)
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0

print()
print("=== 回聊天发一句（ASCII）===")
sh("input", "keyevent", "KEYCODE_BACK")
time.sleep(2)
sh("input", "keyevent", "KEYCODE_BACK")
time.sleep(3)
z = dump("v7")
if not box("聊天", z):
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
    z = dump("v8")
tap(box("聊天", z))
time.sleep(5)
z = dump("v9")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
if not m:
    print("   ✗ 无输入框")
    sys.exit(1)
b = tuple(int(m.group(i)) for i in (1, 2, 3, 4))
sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
time.sleep(2)
sh("input", "text", "hello")
time.sleep(3)
z = dump("v10")
print("   框内:", [t for t in texts(z) if "hello" in t][:1], "；↑ =", boxes("↑", z))
ups = boxes("↑", z)
if ups:
    tap(ups[0])
time.sleep(5)

print("   等待回复与朗读（最多 120 秒）…")
for k in range(12):
    time.sleep(10)
    if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
        new = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
        if "/infer" in new:
            print("   %3ds ✓ F5 收到 /infer" % ((k + 1) * 10))
            break
    if k % 4 == 3:
        print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("v11"))[-4:]))

print()
print("=== ★ 手机端 voice.log ===")
dst = os.path.join(TMP, "phone_voice2.log")
subprocess.run([ADB, "pull", VOICELOG, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有 voice.log ✗ → speak() 仍未被执行）")

print("=== F5 日志新增 ===")
if os.path.isfile(F5LOG):
    t = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
    for l in t.splitlines()[-6:]:
        print("   " + l.strip()[:120])
print()
print("=== 判定 ===")
if "成功播放" in content:
    print("   ✅✅ TTS 端到端成功：手机用电脑 F5-TTS 的丛雨音色朗读")
elif content.strip():
    print("   ⚠ speak() 被调用了但失败 → 见 voice.log 的具体原因")
else:
    print("   ✗ speak() 仍未被执行（朗读开关/路径问题）")
