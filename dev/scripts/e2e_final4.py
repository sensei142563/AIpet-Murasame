# -*- coding: utf-8 -*-
"""终极版：输入后把所有 ↑ 逐个点，直到出现新消息；然后验 Jev 与 F5。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
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


def boxes(label, xml):
    return [tuple(int(m.group(i)) for i in (1, 2, 3, 4))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def box(label, xml):
    b = boxes(label, xml)
    return b[0] if b else None


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


api0 = os.path.getsize(APILOG) if os.path.isfile(APILOG) else 0
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
sh("logcat", "-c")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("h0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
b = box("聊天", dump("h1"))
if b:
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
time.sleep(6)

z = dump("h2")
base_texts = set(texts(z))
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
if not m:
    print("✗ 无输入框")
    sys.exit(1)
ix1, iy1, ix2, iy2 = (int(m.group(i)) for i in (1, 2, 3, 4))
sh("input", "tap", str((ix1 + ix2) // 2), str((iy1 + iy2) // 2))
time.sleep(1)
sh("input", "text", "hello")
time.sleep(3)
z = dump("h3")
ups = boxes("↑", z)
print("输入后所有 ↑ 的位置:", ups)

sent = False
for i, ub in enumerate(ups):
    sh("input", "tap", str((ub[0] + ub[2]) // 2), str((ub[1] + ub[3]) // 2))
    print("   点了第 %d 个 ↑ %s" % (i + 1, ub))
    time.sleep(4)
    z2 = dump("h4_%d" % i)
    tx = texts(z2)
    new = [t for t in tx if t not in base_texts and t != "hello"]
    print("      新文字:", new[-4:])
    if new:
        sent = True
        break

print()
print("=== 等回复 / Jev（最多 110 秒）===")
hit = ""
for k in range(11):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            hit = new
            break
    if k % 4 == 3:
        print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("h5"))[-5:]))

print()
print("=== 手机端 JevClient 日志 ===")
lg = sh("logcat", "-d", "-s", "JevClient:I", t=120)
print("\n".join(("   " + l.strip()[:134]) for l in (lg or "").splitlines()[-14:]) or "   （无）")

time.sleep(20)
print()
print("=== F5 ===")
f5ok = False
if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
    new5 = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
    f5ok = "/infer" in new5
    print("   含 /infer:", f5ok)
    if f5ok:
        print("\n".join(("      " + l.strip()[:124]) for l in new5.splitlines()[-5:]))
else:
    print("   无新增")

print()
print("=== 最终判定 ===")
print("   发送成功 :", "✓" if sent else "✗")
print("   ① Jev    :", "✓ 成立（api 有 /jev/choose）" if hit else "✗ 未触发")
print("   ② F5     :", "✓ 成立（有 /infer）" if f5ok else "✗ 未触发")
if hit:
    print("   api 新增片段:")
    print("\n".join(("      " + l.strip()[:120]) for l in hit.splitlines()[-5:]))
p = os.path.join(TMP, "e2e_final4.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
