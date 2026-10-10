# -*- coding: utf-8 -*-
"""闭环验收：① 手机发消息 → 看 api 日志 /jev/choose 与手机 logcat JevClient
            ② 点回复的 🔊 → 看 F5 日志 /infer。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
REPO = r"E:\university\order\python\pet\AIpet-Murasame-main"
DEV = os.path.join(REPO, "dev")
APILOGS = [os.path.join(DEV, "_api_serve.log"), os.path.join(DEV, "api.log"),
           r"E:\university\order\python\pet\_audit_fish9269\_api_serve.log"]
F5LOGS = [os.path.join(DEV, "_f5serve.log"), os.path.join(DEV, "f5.log"),
          r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"]
TMP = os.path.join(DEV, "shots")
os.makedirs(TMP, exist_ok=True)


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


def desc(pat, xml):
    m = re.search(r'content-desc="([^"]*%s[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % pat, xml)
    return None if not m else (m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def size_of(paths):
    return {p: (os.path.getsize(p) if os.path.isfile(p) else -1) for p in paths}


api0 = size_of(APILOGS)
f50 = size_of(F5LOGS)
print("=== 起点 ===")
for p, s in list(api0.items()) + list(f50.items()):
    print("   %-70s %s" % (os.path.basename(p), s))

print()
print("=== ① 进聊天并发一句话 ===")
sh("logcat", "-c")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("w0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("w1")))
time.sleep(6)
z = dump("w2")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
print("   输入框:", bool(m))
if m:
    b = tuple(int(m.group(i)) for i in (1, 2, 3, 4))
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    time.sleep(1)
    sh("input", "text", "今天有点累")
    time.sleep(2)
    z = dump("w3")
    sent = False
    for pat in ("发送", "send", "\\u27a4", "\\u2191"):
        d = desc(pat, z)
        if d:
            sh("input", "tap", str((d[1] + d[3]) // 2), str((d[2] + d[4]) // 2))
            print("   已点发送按钮:", d[0])
            sent = True
            break
    if not sent:
        for lbl in ("发送", "➤", "↑"):
            if tap(box(lbl, z)):
                print("   已点:", lbl)
                sent = True
                break
    if not sent:
        sh("input", "keyevent", "KEYCODE_ENTER")
        print("   用回车发送")
    time.sleep(5)

print("   等待回复与 Jev 调用（最多 100 秒）…")
api_hit = ""
for k in range(10):
    time.sleep(10)
    for p in APILOGS:
        if os.path.isfile(p) and os.path.getsize(p) > api0[p] >= 0:
            txt = io.open(p, encoding="utf-8", errors="replace").read()
            new = txt[api0[p]:]
            if "/jev/choose" in new:
                api_hit = new
                print("   ✓ %s 出现 /jev/choose" % os.path.basename(p))
                break
    if api_hit:
        break
    if k % 2 == 1:
        z = dump("w4")
        tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
        print("      %3ds 界面尾部: %s" % ((k + 1) * 10, tx[-3:]))

print("=== 手机端 JevClient 日志（logcat）===")
lg = sh("logcat", "-d", "-s", "JevClient:I", "*:S", t=120)
for l in (lg or "").splitlines()[-12:]:
    print("   " + l.strip()[:130])
if not (lg or "").strip():
    print("   （没有 JevClient 日志）")

print()
print("=== ② 点回复上的 🔊 看 F5 ===")
z = dump("w5")
# 找扬声器图标（emoji 编码）或 content-desc 含播放/朗读
d = desc("朗读|播放|speak|volume", z)
if d:
    print("   找到朗读按钮:", d[0])
    sh("input", "tap", str((d[1] + d[3]) // 2), str((d[2] + d[4]) // 2))
else:
    icons = re.findall(r'text="([^"]*(?:128266|128263)[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
    print("   图标候选:", icons[:2])
    if icons:
        _, x1, y1, x2, y2 = icons[0]
        sh("input", "tap", str((int(x1) + int(x2)) // 2), str((int(y1) + int(y2)) // 2))
        print("   已点第一个扬声器图标")
    else:
        print("   ✗ 没找到朗读控件（可能消息行没有该按钮，或者需要长按）")
time.sleep(12)
f5_hit = ""
for p in F5LOGS:
    if os.path.isfile(p) and os.path.getsize(p) > f50[p] >= 0:
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        new = txt[f50[p]:]
        if "/infer" in new:
            f5_hit = new
            print("   ✓ %s 出现 /infer" % os.path.basename(p))
            break

print()
print("=== 判定 ===")
print("   ① 手机 → 电脑 Jev:", "✓ 成立（api 日志有 /jev/choose）" if api_hit else "✗ 未见")
print("   ② 手机 → 电脑 F5 :", "✓ 成立（F5 日志有 /infer）" if f5_hit else "✗ 未见")
p = os.path.join(TMP, "e2e_check.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p, os.path.getsize(p))
