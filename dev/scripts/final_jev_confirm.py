# -*- coding: utf-8 -*-
"""最终确认：单个 ASCII 词 → 点发送（IME 弹出后输入行上移，↑ 即发送键）→ 拉手机日志看"选中"。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
TMP = os.path.join(DEV, "shots")
APILOG = r"E:\university\order\python\pet\_audit_fish9269\_api_serve.log"
NANOLOG = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev\_serve.log"
PHONELOG = "/sdcard/Android/data/com.aipet.murasame/files/jev.log"


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


def boxes(label, xml):
    return [tuple(int(m.group(i)) for i in (1, 2, 3, 4))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def box(label, xml):
    b = boxes(label, xml)
    return b[0] if b else None


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def send_word(word):
    z = dump("y0")
    m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
    if not m:
        print("   ✗ 无输入框")
        return False
    b = tuple(int(m.group(i)) for i in (1, 2, 3, 4))
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    time.sleep(2)
    sh("input", "text", word)
    time.sleep(3)
    z = dump("y1")
    in_field = [t for t in texts(z) if word in t]
    ups = boxes("↑", z)
    print("   输入 %r → 框内 %s ；↑ = %s" % (word, in_field[:1], ups))
    if not in_field:
        print("   ✗ 文本没进框")
        return False
    if not ups:
        print("   ✗ 没有 ↑")
        return False
    tap(ups[0])
    time.sleep(4)
    return True


api0 = os.path.getsize(APILOG) if os.path.isfile(APILOG) else 0
nan0 = os.path.getsize(NANOLOG) if os.path.isfile(NANOLOG) else 0
sh("rm", "-f", PHONELOG)
subprocess.run([ADB, "reverse", "tcp:28565", "tcp:28565"], capture_output=True)
subprocess.run([ADB, "reverse", "tcp:9881", "tcp:9881"], capture_output=True)
print("转发:", subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout.strip().replace("\n", " | "))

sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("y2")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("y3")))
time.sleep(6)

ok = False
for w in ("hello", "hi", "test"):
    print("=== 尝试发送 %r ===" % w)
    if send_word(w):
        ok = True
        break
print("发送动作:", "✓" if ok else "✗")

print("=== 等待（最多 100 秒）===")
for k in range(10):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            print("   %3ds ✓ api 收到 /jev/choose" % ((k + 1) * 10))
            break
    if k % 4 == 3:
        print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("y4"))[-4:]))

print()
print("=== ★ 手机端 jev.log ===")
dst = os.path.join(TMP, "phone_jev_last.log")
subprocess.run([ADB, "pull", PHONELOG, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （空 ✗）")

print("=== 电脑端 ===")
if os.path.isfile(APILOG):
    t = io.open(APILOG, encoding="utf-8", errors="replace").read()
    print("   /jev/choose 累计:", t.count("/jev/choose"))
if os.path.isfile(NANOLOG):
    t2 = io.open(NANOLOG, encoding="utf-8", errors="replace").read()
    print("   NanoJev evaluate 累计:", t2.count("/api/evaluate"))

print()
print("=== 判定 ===")
if "选中" in content:
    print("   ✅✅ Jev 端到端完全成功：手机上出现「选中「…」置信度=…」")
elif "Timeout" in content:
    print("   ⚠ 仍超时（客户端超时或本地首答太慢）")
elif "异常" in content:
    print("   ⚠ 异常：", [l for l in content.splitlines() if "异常" in l][:1])
elif content.strip():
    print("   ⚠ 有日志但未选中：", content.splitlines()[-1][:120])
else:
    print("   ✗ 没有日志（消息可能仍未发出）")
p = os.path.join(TMP, "last_check.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
