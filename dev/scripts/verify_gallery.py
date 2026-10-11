# -*- coding: utf-8 -*-
"""验证拍照进相册：点快门（含坐标微扫）→ 读提示 → 查 MediaStore + 公共目录 → pull 照片。"""
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
PUB = "/sdcard/Pictures/AIpet/"
EXT = "/sdcard/Android/data/%s/files/ar/" % PKG


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


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


# 清掉旧的（便于判定新增）
sh("rm", "-rf", PUB)
print("已清空", PUB, "→", repr(sh("ls", "/sdcard/Pictures/")[:80]))

print("=== 进 AR ===")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("t0")))
time.sleep(5)
tap(box("☰", dump("t1")))
time.sleep(3)
z = dump("t2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
tap(box("AR 模式（实景 + 桌宠）", dump("t3")))
time.sleep(12)
print("   AR:", texts(dump("t4"))[:6])

sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
sx = W // 2
fired = False
for dy in (465, 435, 495, 405, 525):
    sy = H - dy
    print("=== 点快门 (%d,%d) ===" % (sx, sy))
    sh("input", "tap", str(sx), str(sy))
    time.sleep(7)
    z = dump("t5_%d" % dy)
    msgs = [t for t in texts(z) if ("已保存" in t or "失败" in t or "异常" in t or "相册" in t)]
    pub = sh("ls", PUB)
    if msgs or "AIpet_" in pub:
        print("   ★ 提示:", msgs[:2])
        print("   公共目录:", pub.strip() or "(空)")
        fired = True
        break

print()
print("=== MediaStore 里是否有这张（相册靠它扫到）===")
q = sh("content", "query", "--uri", "content://media/external/images/media",
       "--projection", "_display_name:relative_path:date_added",
       "--where", "relative_path LIKE 'Pictures/AIpet%'")
print(q.strip()[:600] or "   （查询为空 —— 相册看不到）")
print()
print("=== 公共目录 ===")
print(sh("ls", "-l", PUB) or "   （空）")
print("=== 应用外部目录 ===")
print(sh("ls", "-l", EXT) or "   （空）")

m2 = re.findall(r"(AIpet_\d+_\d+\.png)", sh("ls", PUB) + sh("ls", EXT))
if m2:
    name = m2[-1]
    for src in (PUB + name, EXT + name):
        dst = os.path.join(TMP, "gallery_%s" % name)
        subprocess.run([ADB, "pull", src, dst], capture_output=True, timeout=180)
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            print("   ✓ pull 到:", dst, os.path.getsize(dst))
            break
p = os.path.join(TMP, "ar_gallery_shot.png")
with io.open(p, "wb") as f:
    q2 = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q2.stdout or b"")
print("   截图:", p)
