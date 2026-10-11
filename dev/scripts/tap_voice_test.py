# -*- coding: utf-8 -*-
"""点设置页「测试电脑语音」→ 等 → pull voice.log + F5 日志判定。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
VL = "/sdcard/Android/data/%s/files/voice.log" % PKG
MARKS = ("☰", "＋", "Live2D", "首页", "记忆", "人设", "设置", "聊天")


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
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
z = dump("t0")
if not any(t in texts(z) for t in MARKS):
    time.sleep(8)
    z = dump("t0b")
print("① 主界面标记:", [t for t in texts(z) if t in MARKS][:5])
tap(box("聊天", z))
time.sleep(5)
z = dump("t1")
tap(box("☰", z))
time.sleep(3)
z = dump("t2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
z = dump("t3")
row = box("测试电脑语音", z)
print("② 「测试电脑语音」行:", row)
if not row:
    # 往下滚找
    for i in range(3):
        sh("input", "swipe", "612", "1600", "612", "900", "350")
        time.sleep(2)
        z = dump("t4_%d" % i)
        row = box("测试电脑语音", z)
        if row:
            break
    print("   滚动后:", row)
sh("rm", "-f", VL)
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
print("③ 点它 …")
tap(row)
print("   等待合成与播放（最多 60 秒）…")
for k in range(6):
    time.sleep(10)
    if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
        new = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
        if "/infer" in new:
            print("   %2ds ✓ F5 收到 /infer" % ((k + 1) * 10))
            break
    print("   %2ds …" % ((k + 1) * 10))

print()
print("=== ★ 手机端 voice.log ===")
dst = os.path.join(TMP, "phone_voice5.log")
subprocess.run([ADB, "pull", VL, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有 ✗）")
print("=== 判定 ===")
if "成功播放" in content:
    print("   ✅✅✅ TTS 端到端成功：手机正在用电脑 F5-TTS 的丛雨音色播放")
elif content.strip():
    print("   ⚠ 调用了但失败 →", [l for l in content.splitlines() if any(k in l for k in ("异常", "失败", "RIFF", "太小", "HTTP"))][:2])
else:
    print("   ✗ speak() 仍未执行（可能没点到那一行）")
print("=== 截图 ===")
p = os.path.join(TMP, "voice_test_row.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   ", p)
