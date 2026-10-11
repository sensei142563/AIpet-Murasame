# -*- coding: utf-8 -*-
"""重新装上 80dp 抬升 + 装完先关华为市场弹窗 + 再测点「聊天」。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
F = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {'''
new = '''                NavigationBar(
                    // 手势导航机型（无可见导航栏）底部约 250px 会被系统 HOME 手势吃掉：
                    // 实测点 y2641 会直接回桌面。显式抬 80dp(≈240px)，把 tab 放到手势区之上。
                    modifier = Modifier.padding(bottom = 80.dp),
                    containerColor = MaterialTheme.colorScheme.surface
                ) {'''
if old in t and "80.dp" not in t:
    t = t.replace(old, new, 1)
    for imp in ("import androidx.compose.foundation.layout.padding", "import androidx.compose.ui.unit.dp"):
        if imp not in t:
            t = t.replace("import androidx.compose.foundation.layout.WindowInsets",
                          "import androidx.compose.foundation.layout.WindowInsets\n" + imp, 1)
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 80dp 抬升已装回")
else:
    print("· 已存在或锚点不同")

r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装机：" + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无)"])[-1][:120])


def adb(*a, timeout=180):
    rr = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=timeout)
    return (rr.stdout or "") + (rr.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:95]
    return "(未知)"


def nodes_of(x):
    out = []
    for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x):
        attrs = (m.group("a1") or "") + (m.group("a2") or "")
        tm = re.search(r'text="([^"]*)"', attrs)
        out.append({"text": tm.group(1) if tm else "", "click": 'clickable="true"' in attrs,
                    "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                    "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
    return out


def tap_text(x, label, lift=0):
    ns = nodes_of(x)
    for i, nd in enumerate(ns):
        if nd["text"] == label:
            tx, ty = (nd["x1"] + nd["x2"]) // 2, (nd["y1"] + nd["y2"]) // 2
            tgt = None
            for j in range(i - 1, -1, -1):
                c = ns[j]
                if c["click"] and c["x1"] <= tx <= c["x2"] and c["y1"] <= ty <= c["y2"]:
                    tgt = c
                    break
            tgt = tgt or nd
            cx, cy = (tgt["x1"] + tgt["x2"]) // 2, (tgt["y1"] + tgt["y2"]) // 2 - lift
            adb("shell", "input", "tap", str(cx), str(cy))
            return (cx, cy, nd["y1"], nd["y2"], tgt["y1"], tgt["y2"])
    return None


print()
print("=== 关华为市场弹窗 ===")
xm = dump("mkt2")
for label in ("完成", "开启"):
    if tap_text(xm, label):
        print("   点了「%s」" % label)
        time.sleep(3)
        break
else:
    adb("shell", "am", "force-stop", "com.huawei.appmarket")
    time.sleep(2)
print("   前台:", fg())

print()
print("=== 启动 App → 点「聊天」===")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
x0 = dump("z1")
print("   启动后前台:", fg())
info = tap_text(x0, "聊天")
print("   文字 y %s~%s；可点祖先 y %s~%s → 点 (%d,%d)" % (info[2], info[3], info[4], info[5], info[0], info[1]))
time.sleep(5)
x1 = dump("z2")
print("   点击后前台:", fg())
v = []
for m in re.finditer(r'text="([^"]{1,24})"', x1):
    if m.group(1) and m.group(1) not in v:
        v.append(m.group(1))
print("   文本:", " | ".join(v[:20]))
print("   判定：仍在 App 内=%s" % (PKG in fg()))
