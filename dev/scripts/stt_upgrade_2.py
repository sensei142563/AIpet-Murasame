# -*- coding: utf-8 -*-
"""STT 升级验收：同一段 16k 样例 → ① 电脑 /stt(large-v3) ② 手机新模型(自检按钮) → 与台词真值对比。"""
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
PKG = "com.aipet.murasame"
DEV = "4BD9K24C06021770"
TMP = os.path.join(MAIN, "dev", "shots")
TRUTH = io.open(os.path.join(MAIN, "dev/scripts/_stt_truth.txt"), encoding="utf-8").read().strip()
WAV = os.path.join(CHAT, "app/src/main/assets/asr-zh-bilingual/selftest.wav")
print("真值:", TRUTH)

print()
print("=== ① 电脑 large-v3（/stt）===")
b = io.open(WAV, "rb").read()
req = urllib.request.Request("http://127.0.0.1:28565/stt", data=b,
                             headers={"Content-Type": "application/octet-stream"})
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.loads(r.read().decode("utf-8", "replace"))
    pc_text = (j.get("text") or "").strip()
    print("   识别: %s   服务端 %sms  往返 %.1fs" % (pc_text, j.get("ms"), time.time() - t0))
except Exception as e:
    pc_text = ""
    print("   ✗", e)

print()
print("=== ② 手机新模型（点设置页「识别自检」）===")


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
    time.sleep(2.5)
    return True


LOG = "/sdcard/Android/data/%s/files/live2d.log" % PKG
before = adb("shell", "wc", "-l", LOG).strip()
print("   live2d.log 之前行数:", before)
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(15)
z = dump("s1")
tap(box("设置", z), "底部导航 设置")
time.sleep(5)
z = dump("s2")
tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
print("   设置页:", [t for t in tx if "自检" in t or "语音" in t][:5])
if not box("识别自检", z):
    for lb in ("语音", "语音服务"):
        if tap(box(lb, z), "进 " + lb):
            time.sleep(3)
            z = dump("s3")
            print("   二级页:", [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()][:8])
            break
tap(box("识别自检", z), "识别自检")
time.sleep(20)
tail = adb("shell", "tail", "-6", LOG)
print("   live2d.log 尾部:")
for l in tail.splitlines():
    print("      " + l.strip()[:150])
m = re.search(r"selftest text=\[(.*?)\]", tail)
phone_text = m.group(1).strip() if m else ""
print()
print("=== 对照 ===")
print("   台词真值      : %s" % TRUTH)
print("   电脑 large-v3 : %s" % (pc_text or "(无)"))
print("   手机新模型    : %s" % (phone_text or "(没拿到，看上面日志)"))
import difflib
if phone_text:
    print("   手机 vs 真值 相似度: %.2f" % difflib.SequenceMatcher(None, TRUTH, phone_text).ratio())
if pc_text:
    print("   电脑 vs 真值 相似度: %.2f" % difflib.SequenceMatcher(None, TRUTH, pc_text).ratio())
