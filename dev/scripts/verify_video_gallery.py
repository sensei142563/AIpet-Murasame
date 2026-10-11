# -*- coding: utf-8 -*-
"""带每步诊断地重验：进 AR → 长按快门录像 → 再长按停止 → 查相册视频表是否出现新 mp4。"""
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


def gallery_videos():
    out = sh("content", "query", "--uri", "content://media/external/video/media",
             "--projection", "_display_name:_data")
    return re.findall(r"_display_name=(AIpet_\d+_\d+\.mp4)", out)


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(15)
print("① 启动后:", texts(dump("w1"))[:6])
tap(box_any(["聊天"], dump("w2")), "聊天")
time.sleep(6)
tap(box_any(["☰"], dump("w3")), "☰")
time.sleep(4)
z = dump("w4")
print("   抽屉:", texts(z)[:6])
tap(box_any(["⚙  设置", "设置"], z), "设置")
time.sleep(4)
z = dump("w5")
print("   设置页:", [t for t in texts(z) if "AR" in t][:3])
tap(box_any(["AR 模式（实景 + 桌宠）"], z), "AR模式")
time.sleep(15)
z = dump("w6")
tx = texts(z)
print("   AR 页:", tx[:14])
if not any(t == "相册" for t in tx) and not any("点按拍照" in t for t in tx):
    print("   ✗ 没进 AR 页，放弃本次验证")
    sys.exit(1)
a = box_any(["相册"], z)
sy = ((a[1] + a[3]) // 2) if a else 2123
print()
print("② 长按快门 (612,%d) 开始录像" % sy)
sh("input", "swipe", "612", str(sy), "612", str(sy), "900")
time.sleep(6)
print("   状态:", [t for t in texts(dump("w7")) if "REC" in t or "录像" in t][:2])
time.sleep(8)
print("③ 再长按停止")
sh("input", "swipe", "612", str(sy), "612", str(sy), "900")
time.sleep(10)
z = dump("w8")
print("   提示:", [t for t in texts(z) if "已保存" in t or "失败" in t][:2])
print()
print("④ 相册视频表里的 AIpet_*.mp4:", gallery_videos())
print("   ar/ 目录最新三个:")
for l in sh("ls", "-l", "/sdcard/Android/data/com.aipet.murasame/files/ar/").strip().splitlines()[-3:]:
    print("      " + l)
