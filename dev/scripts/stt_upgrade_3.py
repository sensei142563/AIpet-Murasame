# -*- coding: utf-8 -*-
"""修 selfTest（每次都从 assets 重新复制样例）→ 编译装机 → 稳妥点击「识别自检」→ 与真值/电脑对照。"""
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
ONLINE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/OnlineAsr.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
DEV = "4BD9K24C06021770"
TMP = os.path.join(MAIN, "dev", "shots")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① selfTest 每次都重新复制样例 ----------
s = io.open(ONLINE, encoding="utf-8").read().replace("\r\n", "\n")
old = """            val f = File(ctx.filesDir, "selftest.wav")
            if (!f.exists() || f.length() == 0L) {
                ctx.assets.open("$DIR/selftest.wav").use { ins -> f.outputStream().use { ins.copyTo(it) } }
            }"""
new = """            val f = File(ctx.filesDir, "selftest.wav")
            // 每次都从 assets 重新复制：换了模型/换了样例时，旧的 filesDir/selftest.wav 会让自检结果失真
            ctx.assets.open("$DIR/selftest.wav").use { ins -> f.outputStream().use { ins.copyTo(it) } }"""
if old in s:
    s = s.replace(old, new, 1)
    io.open(ONLINE, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ selfTest 改为每次重新复制样例")
else:
    print("· 未找到旧实现（可能已改）")

print("=== 编译装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:6]:
    print("   " + y[:230])
if r.returncode != 0:
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
rr = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装:", ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:60])


def adb(*a, t=300):
    return subprocess.run([ADB, "-s", DEV] + list(a), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


def dump(tag):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=90)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


def tap(bb, tag=""):
    if not bb:
        print("   ✗ 没找到 %s" % tag)
        return False
    adb("shell", "input", "tap", str((bb[0] + bb[2]) // 2), str((bb[1] + bb[3]) // 2))
    print("   tap %s" % tag)
    time.sleep(2)
    return True


def find_with_retry(labels, tries=5, wait=5):
    """反复 dump 直到出现目标文本（页面渲染慢是常态）"""
    for i in range(tries):
        z = dump("r%d" % i)
        for lb in labels:
            b = box(lb, z)
            if b:
                return lb, b, z
        time.sleep(wait)
    return None, None, z


LOG = "/sdcard/Android/data/%s/files/live2d.log" % PKG
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
lb, b, z = find_with_retry(["记忆", "设置"], tries=4)
tap(b, "底部导航 " + str(lb))
time.sleep(6)
target, tb, z = find_with_retry(["识别自检", "测试电脑语音"], tries=5)
print("   找到:", target)
if target == "测试电脑语音":
    # 自检按钮可能在同一页更靠上/下，直接再找一次
    target2, tb2, z2 = find_with_retry(["识别自检"], tries=2, wait=2)
    if target2:
        tb = tb2
        target = target2
print("   live2d.log 之前尾部:", adb("shell", "tail", "-1", LOG).strip()[:100])
tap(tb, "点 " + str(target))
time.sleep(22)
tail = adb("shell", "tail", "-4", LOG)
print("   live2d.log 之后尾部:")
for l in tail.splitlines():
    print("      " + l.strip()[:150])
m = re.search(r"selftest text=\[(.*?)\]", tail)
phone_text = m.group(1).strip() if m else ""
TRUTH = io.open(os.path.join(MAIN, "dev/scripts/_stt_truth.txt"), encoding="utf-8").read().strip()
print()
print("=== 对照 ===")
print("   真值        : %s" % TRUTH)
print("   手机新模型  : %s" % (phone_text or "(没拿到)"))
import difflib
if phone_text:
    print("   相似度      : %.2f" % difflib.SequenceMatcher(None, TRUTH, phone_text).ratio())
