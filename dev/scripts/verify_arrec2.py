# -*- coding: utf-8 -*-
"""复验 AR 录屏（带每步诊断）：授权框点「允许」，停止后查 AR_*.mp4 并列目录。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
ARDIR = "/sdcard/Android/data/%s/files/ar/" % PKG


def sh(*a, t=300):
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


def box_any(labels, xml):
    for lb in labels:
        m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(lb), xml)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def tap(b, tag=""):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        print("   tap %s %s" % (tag, b))
        return True
    print("   ✗ 没找到 %s" % tag)
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(14)
print("① 启动后文字:", texts(dump("c0"))[:8])
tap(box_any(["聊天"], dump("c1")), "聊天")
time.sleep(6)
tap(box_any(["☰"], dump("c2")), "☰")
time.sleep(4)
z = dump("c3")
print("   抽屉文字:", texts(z)[:8])
tap(box_any(["⚙  设置", "设置"], z), "设置")
time.sleep(4)
z = dump("c4")
print("   设置页文字:", [t for t in texts(z) if "AR" in t or "模式" in t][:4])
tap(box_any(["AR 模式（实景 + 桌宠）"], z), "AR模式")
time.sleep(14)
z = dump("c5")
print("   AR 页文字:", texts(z)[:14])
b = box_any(["AR录屏"], z)
print("② AR录屏按钮:", b)
if not b:
    print("   ✗ 未找到按钮，放弃本轮")
    sys.exit(1)
tap(b, "AR录屏")
time.sleep(6)
z = dump("c6")
print("   授权框:", [t for t in texts(z) if "允许" in t or "禁止" in t][:3])
tap(box_any(["允许"], z), "允许")
time.sleep(8)
z = dump("c7")
print("③ 录屏中提示:", [t for t in texts(z) if "录屏" in t or "失败" in t][:2])
time.sleep(10)
tap(box_any(["AR录屏"], dump("c8")), "AR录屏(停)")
time.sleep(8)
z = dump("c9")
print("④ 停止后提示:", [t for t in texts(z) if "已保存" in t or "失败" in t][:2])
print("⑤ ar/ 目录尾部:", (sh("ls", "-l", ARDIR).strip().splitlines() or ["(空)"])[-3:])
v = re.findall(r"(AR_\d+_\d+\.mp4)", sh("ls", ARDIR))
print("   AR_*.mp4:", v)
if v:
    dst = os.path.join(TMP, "arrec_" + v[-1])
    subprocess.run([ADB, "pull", ARDIR + v[-1], dst], capture_output=True, timeout=300)
    print("   ✓ pull:", dst, os.path.getsize(dst) if os.path.exists(dst) else 0)
    ff = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_name,width,height,duration", "-of", "default=noprint_wrappers=1", dst],
                        capture_output=True, text=True, timeout=120)
    print("   ffprobe:", (ff.stdout or ff.stderr or "").replace("\n", " ")[:200])
