# -*- coding: utf-8 -*-
"""坐标试探发送按钮：输入 hello 后依次点两个候选，每次看消息是否出现 → 成功后验 Jev/F5。"""
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


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


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
    if box("聊天", dump("g0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tapc = box("聊天", dump("g1"))
if tapc:
    sh("input", "tap", str((tapc[0] + tapc[2]) // 2), str((tapc[1] + tapc[3]) // 2))
time.sleep(6)

z = dump("g2")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
if not m:
    print("✗ 无输入框")
    sys.exit(1)
ix1, iy1, ix2, iy2 = (int(m.group(i)) for i in (1, 2, 3, 4))
before = texts(z)
print("输入行: (%d,%d)-(%d,%d)；当前可见文字数 %d" % (ix1, iy1, ix2, iy2, len(before)))

# 候选按钮中心（来自历次 dump 的输入行右侧 View）
cands = [((824 + 945) // 2, (2348 + 2506) // 2, "候选A(824-945)"),
         ((945 + 1107) // 2, (2348 + 2506) // 2, "候选B(945-1107)"),
         ((751 + 974) // 2, (2506 + 2776) // 2, "候选C(751-974,下方)")]

sent = False
for cx, cy, name in cands:
    z = dump("g3")
    m2 = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
    if m2:
        b = tuple(int(m2.group(i)) for i in (1, 2, 3, 4))
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        time.sleep(1)
    sh("input", "text", "hello")
    time.sleep(2)
    z = dump("g4")
    if not re.findall(r'text="([^"]*hello[^"]*)"', z):
        print("   %s：文本没进去，跳过" % name)
        continue
    sh("input", "tap", str(cx), str(cy))
    time.sleep(4)
    z = dump("g5")
    tx = texts(z)
    newtxt = [t for t in tx if t not in before]
    print("   %s → 点(%d,%d)；新增文字: %s" % (name, cx, cy, newtxt[-4:]))
    if "hello" not in tx or any(t != "hello" for t in newtxt):
        if newtxt:
            sent = True
            print("   ★ 可能发送成功")
            break

print()
print("=== 等回复 / Jev（最多 100 秒）===")
hit = ""
for k in range(10):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            hit = new
            break
    if k % 4 == 3:
        print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("g6"))[-5:]))

print()
print("=== 手机端 JevClient 日志 ===")
lg = sh("logcat", "-d", "-s", "JevClient:I", t=120)
print("\n".join(("   " + l.strip()[:134]) for l in (lg or "").splitlines()[-14:]) or "   （无）")

time.sleep(20)
print()
print("=== F5 ===")
if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
    new5 = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
    print("   含 /infer:", "/infer" in new5)
else:
    print("   无新增")
print()
print("判定：① Jev", "✓" if hit else "✗", "；发送是否成功:", "✓" if sent else "✗")
p = os.path.join(TMP, "e2e_final3.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("截图:", p)
