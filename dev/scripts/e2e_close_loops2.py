# -*- coding: utf-8 -*-
"""闭环验收（修正版）：ASCII 文本 + 打印输入框附近的可点击节点找发送按钮 → 看 Jev 日志。"""
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


api0 = os.path.getsize(APILOG) if os.path.isfile(APILOG) else 0
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
print("起点：api=%d f5=%d" % (api0, f50))

sh("logcat", "-c")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("x0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("x1")))
time.sleep(6)

z = dump("x2")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
assert m, "✗ 没找到聊天输入框"
ix1, iy1, ix2, iy2 = (int(m.group(i)) for i in (1, 2, 3, 4))
print("输入框 bounds:", (ix1, iy1, ix2, iy2))

print("=== 输入框同一横带上的可点击节点（找发送按钮）===")
cands = []
for mm in re.finditer(r'<node[^>]*>', z):
    tag = mm.group(0)
    if 'clickable="true"' not in tag:
        continue
    b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
    if not b:
        continue
    x1, y1, x2, y2 = (int(b.group(i)) for i in (1, 2, 3, 4))
    cy = (y1 + y2) // 2
    if iy1 - 140 <= cy <= iy2 + 140 and x2 >= ix2:
        d = re.search(r'content-desc="([^"]*)"', tag)
        t2 = re.search(r'text="([^"]*)"', tag)
        cls = re.search(r'class="([^"]*)"', tag)
        cands.append((x1, y1, x2, y2, (t2.group(1) if t2 else ""), (d.group(1) if d else ""),
                      (cls.group(1) if cls else "").split(".")[-1]))
for c in cands:
    print("   bounds=(%d,%d)-(%d,%d) text=%r desc=%r cls=%s" % c)

# 输入 ASCII 文本（adb input text 不支持中文）
sh("input", "tap", str((ix1 + ix2) // 2), str((iy1 + iy2) // 2))
time.sleep(1)
sh("input", "text", "hello")
time.sleep(2)
z = dump("x3")
print("输入后框内:", re.findall(r'text="([^"]*hello[^"]*)"', z)[:2])

sent = False
# 优先用「在输入框右侧」的最靠右节点
if cands:
    cands.sort(key=lambda c: -c[2])
    c = cands[0]
    sh("input", "tap", str((c[0] + c[2]) // 2), str((c[1] + c[3]) // 2))
    print("已点最右侧候选:", c[4] or c[5] or c[6])
    sent = True
if not sent:
    sh("input", "keyevent", "KEYCODE_ENTER")
    print("用回车发送")
time.sleep(4)

print("=== 等待回复 / Jev 调用（最多 100 秒）===")
hit = ""
for k in range(10):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            hit = new
            break
    if k % 3 == 2:
        z = dump("x4")
        tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
        print("   %3ds 尾部: %s" % ((k + 1) * 10, tx[-4:]))

print()
print("=== 手机端 JevClient 日志 ===")
lg = sh("logcat", "-d", "-s", "JevClient:I", t=120)
print("\n".join(("   " + l.strip()[:132]) for l in (lg or "").splitlines()[-12:]) or "   （无）")
print()
print("=== 判定 ===")
print("   手机 → 电脑 Jev:", "✓ 成立" if hit else "✗ 未触发")
if hit:
    print("   api 日志新增:", "\n".join(("      " + l.strip()[:120]) for l in hit.splitlines()[-4:]))

print()
print("=== 点 🔇/🔊 开关打开朗读后，再发一句看 F5 ===")
z = dump("x5")
for lbl in ("&#128263;", "&#128266;"):
    if box(lbl, z):
        tap(box(lbl, z))
        print("   已点音量图标:", lbl)
        break
time.sleep(2)
z = dump("x6")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
if m:
    b = tuple(int(m.group(i)) for i in (1, 2, 3, 4))
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    time.sleep(1)
    sh("input", "text", "hi again")
    time.sleep(2)
    if cands:
        c = cands[0]
        sh("input", "tap", str((c[0] + c[2]) // 2), str((c[1] + c[3]) // 2))
    else:
        sh("input", "keyevent", "KEYCODE_ENTER")
    print("   已再发一句（朗读已开）")
time.sleep(45)
if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
    new5 = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
    print("   F5 日志新增含 /infer:", "/infer" in new5)
    if "/infer" in new5:
        print("\n".join(("      " + l.strip()[:120]) for l in new5.splitlines()[-5:]))
else:
    print("   F5 日志无新增 ✗")
p = os.path.join(TMP, "e2e_close_loops2.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("截图:", p)
