# -*- coding: utf-8 -*-
"""补验：长按快门(612, 2123) = 开始/停止录像 → 查新 mp4 + ffprobe。"""
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


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def vids():
    return re.findall(r"(AIpet_\d+_\d+\.mp4)", sh("ls", ARDIR))


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(14)
tap(box_any(["聊天"], dump("n0")))
time.sleep(6)
tap(box_any(["☰"], dump("n1")))
time.sleep(4)
z = dump("n2")
tap(box_any(["⚙  设置", "设置"], z))
time.sleep(4)
tap(box_any(["AR 模式（实景 + 桌宠）"], dump("n3")))
time.sleep(14)
z = dump("n4")
a = box_any(["相册"], z)
ft = box_any(["翻转"], z)
sx = 612
sy = ((a[1] + a[3]) // 2) if a else 2123
print("① 相册 %s 翻转 %s → 快门中心推定 (%d,%d)" % (a, ft, sx, sy))
v0 = vids()
print("   录前 mp4:", v0)
print("② 长按快门 900ms …")
sh("input", "swipe", str(sx), str(sy), str(sx), str(sy), "900")
time.sleep(5)
z = dump("n5")
st = [t for t in texts(z) if "录像中" in t or "REC" in t or "失败" in t]
print("   状态:", st[:2])
time.sleep(9)
print("③ 再长按一次停止 …")
sh("input", "swipe", str(sx), str(sy), str(sx), str(sy), "900")
time.sleep(9)
z = dump("n6")
print("   提示:", [t for t in texts(z) if "已保存" in t or "失败" in t or "录像" in t][:2])
v1 = vids()
print("④ ar/ 里 mp4:", v1, "（新增 %d）" % (len(v1) - len(v0)))
if v1 and v1[-1] not in v0:
    dst = os.path.join(TMP, "longpress2_" + v1[-1])
    subprocess.run([ADB, "pull", ARDIR + v1[-1], dst], capture_output=True, timeout=300)
    print("   ✓ pull:", dst, os.path.getsize(dst) if os.path.exists(dst) else 0)
    ff = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_name,width,height,duration", "-of", "default=noprint_wrappers=1", dst],
                        capture_output=True, text=True, timeout=120)
    print("   ffprobe:", (ff.stdout or ff.stderr or "").replace("\n", " ")[:200])
p = os.path.join(TMP, "ar_longpress_rec.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p, os.path.getsize(p))
