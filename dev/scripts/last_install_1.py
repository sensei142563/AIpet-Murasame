# -*- coding: utf-8 -*-
"""最后一次装机窗口：按优先级一次做完（安装 → 推测试 VRM → 验 VRM 页 → 验 QQ 页）。
   手机若已拿走，本脚本会干净退出并提示。"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
VRM_SRC = os.path.join(MAIN, "dev", "three-demo", "VRM1_Constraint_Twist_Sample.vrm")
SHOTS = os.path.join(MAIN, "dev", "shots")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def adb(*a, t=600):
    return subprocess.run([ADB, "-s", DEV] + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


def shot(tag):
    p = os.path.join(SHOTS, tag + ".png")
    r = subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"],
                       capture_output=True, timeout=180)
    if r.stdout and len(r.stdout) > 10000:
        io.open(p, "wb").write(r.stdout)
        return p
    return None


print("=== 设备 ===")
devs = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=60).stdout
print("   " + " ".join(devs.split()))
if DEV not in devs:
    print("手机不在线（可能已被拿走）→ 本轮只做不依赖手机的工作")
    sys.exit(0)

print("=== ① 安装最新 APK（含 QQ 页 / VRM 页 / 离线 TTS 接线 / ArGround）===")
print("   APK %.1f MB  构建时间 %s" % (os.path.getsize(APK) / 1e6,
      time.strftime("%m-%d %H:%M:%S", time.localtime(os.path.getmtime(APK)))))
r = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   " + ((r.stdout or r.stderr or "").strip().splitlines() or [""])[-1][:70])
t = adb("shell", "dumpsys", "package", PKG)
m = re.search(r"lastUpdateTime=([^\n]+)", t)
print("   lastUpdateTime:", (m.group(1).strip() if m else "?"))
note("安装完成", bool(m))

print("=== ② 推测试 VRM 到应用外部目录（不入库的测试资产）===")
dst = "/sdcard/Android/data/%s/files/vrm" % PKG
adb("shell", "mkdir", "-p", dst)
r = subprocess.run([ADB, "-s", DEV, "push", VRM_SRC, dst + "/model.vrm"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
print("   " + ((r.stdout or r.stderr or "").strip().splitlines() or [""])[-1][:90])
print("   " + adb("shell", "ls", "-l", dst + "/model.vrm").strip()[:120])


def tap_text(label, tries=6, wait=4):
    for i in range(tries):
        adb("shell", "uiautomator", "dump", "/sdcard/d.xml")
        subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/d.xml", os.path.join(SHOTS, "d.xml")],
                       capture_output=True, timeout=90)
        try:
            x = io.open(os.path.join(SHOTS, "d.xml"), encoding="utf-8", errors="replace").read()
        except Exception:
            x = ""
        mm = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), x)
        if mm:
            cx = (int(mm.group(1)) + int(mm.group(3))) // 2
            cy = (int(mm.group(2)) + int(mm.group(4))) // 2
            adb("shell", "input", "tap", str(cx), str(cy))
            time.sleep(2.5)
            return x
        time.sleep(wait)
    return ""


print("=== ③ 打开 App → VRM 演示页 ===")
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(2)
adb("shell", "logcat", "-c")
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(15)
x = tap_text("聊天")
time.sleep(3)
tap_text("☰")
time.sleep(2)
x = tap_text("🧍 VRM 演示（3D 的她）")
if not x:
    x = tap_text("VRM 演示")
time.sleep(10)
p = shot("last_vrm_page")
print("   截图:", p or "(没拍到)")
log = adb("shell", "cat", "/sdcard/Android/data/%s/files/vrm.log" % PKG)
print("   vrm.log 末几行:")
for l in (log or "").strip().splitlines()[-4:]:
    print("      " + l.strip()[:140])
note("页面已打开（看到标题或日志）", ("VRM" in x) or ("title=" in log))

print("=== ④ QQ 通道页 ===")
adb("shell", "input", "keyevent", "KEYCODE_BACK")
time.sleep(2)
tap_text("聊天")
time.sleep(2)
tap_text("☰")
time.sleep(2)
x = tap_text("💬 QQ 通道")
if not x:
    x = tap_text("QQ 通道")
time.sleep(8)
p = shot("last_qq_page")
print("   截图:", p or "(没拍到)")
try:
    z = io.open(os.path.join(SHOTS, "d.xml"), encoding="utf-8", errors="replace").read()
    tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
    print("   页面文字:")
    for t in tx[:14]:
        print("      " + t[:100])
    note("QQ 页显示了 NapCat 状态", any("NapCat" in t for t in tx))
    note("QQ 页显示了会话/队列信息", any(("会话" in t) or ("待发送" in t) for t in tx))
except Exception as e:
    print("   读 dump 失败:", e)

print("=== ⑤ 日志里有没有 TTS/语音链路线索 ===")
for f in ("live2d.log", "voice.log"):
    c = adb("shell", "cat", "/sdcard/Android/data/%s/files/%s" % (PKG, f))
    lines = [l for l in (c or "").strip().splitlines() if l.strip()][-5:]
    print("   %s:" % f)
    for l in lines:
        print("      " + l.strip()[:150])
print()
print("总结:", "最后一次装机窗口内的验收完成 ✓" if ok else "有未完成项（见上）✗")
