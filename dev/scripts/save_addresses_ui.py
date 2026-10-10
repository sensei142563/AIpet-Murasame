# -*- coding: utf-8 -*-
"""用自动化进设置页把两个地址真正填好并点「保存」，再 pull jev.log 确认 baseUrl 生效。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"


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


def edittext(xml):
    m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
    return None if not m else tuple(int(m.group(i)) for i in (1, 2, 3, 4))


def tap(b, name=""):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        print("      已点", name)
        return True
    print("      ✗ 没找到", name)
    return False


def fill(row, value):
    print("   --- 处理:", row)
    tap(box(row, dump("p1")), row)
    time.sleep(3)
    z = dump("p2")
    tf = edittext(z)
    if not tf:
        print("      ✗ 没有输入框（对话框没开？）")
        return False
    sh("input", "tap", str((tf[0] + tf[2]) // 2), str((tf[1] + tf[3]) // 2))
    time.sleep(1)
    sh("input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(80):
        sh("input", "keyevent", "KEYCODE_DEL")
    time.sleep(1)
    z = dump("p3")
    left = [t for t in re.findall(r'text="(http[^"]*)"', z)]
    print("      清空后:", left[:1] or "（空 ✓）")
    sh("input", "text", value)
    time.sleep(1)
    z = dump("p4")
    got = [t for t in re.findall(r'text="(http[^"]*)"', z)]
    print("      填入后:", got[:2])
    ok = tap(box("保存", z), "保存")
    time.sleep(3)
    z = dump("p5")
    now = [t for t in re.findall(r'text="([^"]*)"', z) if "127.0.0.1" in t or "172.25" in t]
    print("      行上显示:", now[:2])
    return ok


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("q0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("q1")), "聊天")
time.sleep(5)
tap(box("☰", dump("q2")), "☰")
time.sleep(3)
z = dump("q3")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z), "设置")
time.sleep(3)

fill("Jev 电脑地址", "http://127.0.0.1:28565")
fill("语音服务地址", "http://127.0.0.1:9881")

print()
print("=== 验证：重开 App 后地址是否还在（冷启动 load）===")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
z = dump("q9")
for t in range(6):
    if box("聊天", z):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
    z = dump("q9")
tap(box("聊天", z), "聊天")
time.sleep(5)
tap(box("☰", dump("qa")), "☰")
time.sleep(3)
z = dump("qb")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z), "设置")
time.sleep(3)
z = dump("qc")
print("   冷启动后设置页显示:", [t for t in re.findall(r'text="([^"]*)"', z) if "127.0.0.1" in t or "未启用" in t or "电脑IP" in t][:3])
print()
print("=== 对照：手机端 jev.log（外部可读）===")
subprocess.run([ADB, "pull", "/sdcard/Android/data/com.aipet.murasame/files/jev.log",
                os.path.join(TMP, "phone_jev2.log")], capture_output=True, text=True, encoding="utf-8",
               errors="replace", timeout=120)
p = os.path.join(TMP, "phone_jev2.log")
if os.path.isfile(p):
    print("\n".join("   " + l for l in io.open(p, encoding="utf-8", errors="replace").read().splitlines()[-6:]))
