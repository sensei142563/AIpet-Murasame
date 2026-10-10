# -*- coding: utf-8 -*-
"""实测：点消息上的 🔊 → 看 F5 日志是否收到手机发来的 /infer。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\_audit_fish9269"
F5LOG = os.path.join(TMP, "_f5serve.log")


def sh(*a, t=180):
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


def tap(b, label=""):
    if not b:
        print("      ✗ 找不到 " + label)
        return False
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    print("      已点 " + label)
    return True


before = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
print("=== F5 日志起点: %d 字节 ===" % before)
print("=== reverse:", subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace").stdout.strip().replace("\n", " | "))

sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for _ in range(4):
    z = dump("q0")
    if box("聊天", z):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("q1")), "聊天")
time.sleep(6)

z = dump("q2")
# 找 🔊（emoji 编码成 &#128266;）或 content-desc 含朗读
cands = re.findall(r'(?:text|content-desc)="([^"]*(?:128266|朗读|播放|speak)[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
print("   找到的朗读按钮:", cands[:3])
if cands:
    _, x1, y1, x2, y2 = cands[0]
    sh("input", "tap", str((int(x1) + int(x2)) // 2), str((int(y1) + int(y2)) // 2))
    print("      已点第一个 🔊")
else:
    # 兜底：点消息气泡附近
    m = re.search(r'text="([^"]{6,})"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
    if m:
        x1, y1, x2, y2 = (int(m.group(i)) for i in (2, 3, 4, 5))
        sh("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
        print("      点了一条消息（找 🔊）:", m.group(1)[:20])

print("   等待 F5 被调用（最多 60 秒）…")
hit = ""
for k in range(12):
    time.sleep(5)
    sz = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
    if sz > before:
        new = io.open(F5LOG, encoding="utf-8", errors="replace").read()[before:]
        print("      %2ds 日志新增 %d 字节" % ((k + 1) * 5, sz - before))
        if "/infer" in new:
            hit = new
            break
    else:
        print("      %2ds 无新增" % ((k + 1) * 5))

print()
print("=== 判定 ===")
if hit:
    print("   ✓✓✓ **手机真的调用了电脑 F5-TTS** —— 语音链路成立 ✓")
    for l in hit.splitlines()[-8:]:
        print("      " + l.strip()[:120])
else:
    new = io.open(F5LOG, encoding="utf-8", errors="replace").read()[before:] if os.path.isfile(F5LOG) else ""
    print("   ✗ 没看到 /infer（可能没点到 🔊；也可能请求失败）")
    print("   日志新增:", (new[-400:] or "(无)"))
    z = dump("q9")
    print("   界面尾部:", [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()][-6:])
