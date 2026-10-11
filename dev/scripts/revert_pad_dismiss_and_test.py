# -*- coding: utf-8 -*-
"""① 撤掉 NavigationBar 的 80dp 内边距（不是真因）② 保留 BackHandler 逻辑保险
   ③ 编译装机 ④ **关掉华为市场的"安装成功"弹窗** ⑤ 再测点「聊天」。"""
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
old = '''                NavigationBar(
                    // 手势导航机型底部约 216px 不报 inset 但吃触摸 ⇒ 显式把 tab 抬起来，
                    // 文字中心约 y2455（屏幕高 2776），越出被吞掉的区域。
                    modifier = Modifier.padding(bottom = 80.dp),
                    containerColor = MaterialTheme.colorScheme.surface
                ) {'''
new = '''                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已撤掉 80dp 内边距（恢复原样）")
else:
    print("· 80dp 不在（可能已撤）")
print("   BackHandler 保险是否还在：%s" % ("在 ✓" if "页面切换，就把退出计时清零" in t or "lastBackAt = 0L" in t else "不在 ✗"))

print()
print("=== 编译 + 装机 ===")
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
            return l.strip()[:100]
    return "(未知)"


print()
print("=== 关掉华为市场弹窗（点它的「完成」/「开启」）===")
x = dump("mkt")
print("   当前前台:", fg())
for label in ("完成", "开启", "关闭"):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % label, x)
    if not m:
        m2 = re.search(r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="%s"' % label, x)
        m = m2
    if m:
        cx = (int(m.group(1)) + int(m.group(3))) // 2
        cy = (int(m.group(2)) + int(m.group(4))) // 2
        adb("shell", "input", "tap", str(cx), str(cy))
        print("   点了「%s」(%d,%d)" % (label, cx, cy))
        time.sleep(3)
        break
else:
    print("   没找到按钮，尝试 force-stop 市场")
    adb("shell", "am", "force-stop", "com.huawei.appmarket")
    time.sleep(2)
print("   处理完前台:", fg())

print()
print("=== 重新启动 App 并点「聊天」===")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
x0 = dump("w1")
print("   启动后前台:", fg())
nodes = []
for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x0):
    attrs = (m.group("a1") or "") + (m.group("a2") or "")
    tm = re.search(r'text="([^"]*)"', attrs)
    nodes.append({"text": tm.group(1) if tm else "", "click": 'clickable="true"' in attrs,
                  "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                  "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
tgt = None
for i, nd in enumerate(nodes):
    if nd["text"] == "聊天":
        tx, ty = (nd["x1"] + nd["x2"]) // 2, (nd["y1"] + nd["y2"]) // 2
        for j in range(i - 1, -1, -1):
            c = nodes[j]
            if c["click"] and c["x1"] <= tx <= c["x2"] and c["y1"] <= ty <= c["y2"]:
                tgt = c
                break
        tgt = tgt or nd
        break
if tgt:
    cx = (tgt["x1"] + tgt["x2"]) // 2
    cy = (tgt["y1"] + tgt["y2"]) // 2
    print("   点「聊天」目标 (%d,%d)" % (cx, cy))
    adb("shell", "input", "tap", str(cx), str(cy))
    time.sleep(5)
    x1 = dump("w2")
    print("   点击后前台:", fg())
    v = []
    for m in re.finditer(r'text="([^"]{1,24})"', x1):
        if m.group(1) and m.group(1) not in v:
            v.append(m.group(1))
    print("   文本:", " | ".join(v[:18]))
    ok = PKG in fg()
    chat = any(k in x1 for k in ("发送", "输入", "表情", "语音", "长按"))
    print("   判定：仍在 App 内=%s；像聊天页=%s" % (ok, chat))
else:
    print("   ✗ 没找到「聊天」节点")
