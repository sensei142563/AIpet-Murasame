# -*- coding: utf-8 -*-
"""端到端（三修版）：单词输入 + 只认输入行里的 ↑ → 发送 → 查 Jev 日志与 F5。"""
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


def boxes(label, xml):
    out = []
    for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml):
        out.append(tuple(int(m.group(i)) for i in (1, 2, 3, 4)))
    return out


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


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
    if box("聊天", dump("f0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("f1")))
time.sleep(6)

z = dump("f2")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
assert m, "✗ 无输入框"
ix1, iy1, ix2, iy2 = (int(m.group(i)) for i in (1, 2, 3, 4))
print("输入框:", (ix1, iy1, ix2, iy2))

sh("input", "tap", str((ix1 + ix2) // 2), str((iy1 + iy2) // 2))
time.sleep(1)
sh("input", "text", "hello")
time.sleep(3)
z = dump("f3")
got = re.findall(r'text="([^"]*hello[^"]*)"', z)
print("框内:", got[:2])
ups = boxes("↑", z)
print("所有 ↑ 位置:", ups)
onrow = [b for b in ups if iy1 - 120 <= (b[1] + b[3]) // 2 <= iy2 + 120]
print("输入行里的 ↑:", onrow)
target = onrow[0] if onrow else (ups[0] if ups else None)
if not got:
    print("✗ 文本没进去 —— 放弃本轮（不改动任何东西）")
    sys.exit(1)
tap(target)
print("已点发送:", target)
time.sleep(4)
print("发送后尾部:", texts(dump("f4"))[-4:])

print("=== 等回复 / Jev（最多 110 秒）===")
hit = ""
for k in range(11):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            hit = new
            break
    if k % 3 == 2:
        print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("f5"))[-4:]))

print()
print("=== 手机端 JevClient 日志 ===")
lg = sh("logcat", "-d", "-s", "JevClient:I", t=120)
print("\n".join(("   " + l.strip()[:134]) for l in (lg or "").splitlines()[-14:]) or "   （无）")

print()
print("=== F5（朗读应自动触发）===")
time.sleep(25)
if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
    new5 = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
    print("   含 /infer:", "/infer" in new5)
    if "/infer" in new5:
        print("\n".join(("      " + l.strip()[:124]) for l in new5.splitlines()[-6:]))
else:
    print("   无新增 ✗")

print()
print("=== 判定 ===")
print("   ① 手机→电脑 Jev :", "✓ 成立" if hit else "✗ 未触发")
print("   ② 手机→电脑 F5  :", "见上")
if hit:
    print("   api 新增:", "\n".join(("      " + l.strip()[:120]) for l in hit.splitlines()[-4:]))
p = os.path.join(TMP, "e2e_final2.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
