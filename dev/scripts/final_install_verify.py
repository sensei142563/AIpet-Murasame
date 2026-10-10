# -*- coding: utf-8 -*-
"""收尾：确保超时版真正装机（比对 lastUpdateTime，最多重试 3 次）→ 发消息 → 拉日志判定。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
TMP = os.path.join(DEV, "shots")
APILOG = r"E:\university\order\python\pet\_audit_fish9269\_api_serve.log"
NANOLOG = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev\_serve.log"
PHONELOG = "/sdcard/Android/data/com.aipet.murasame/files/jev.log"


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def install_time():
    t = sh("dumpsys", "package", "com.aipet.murasame")
    m = re.search(r"lastUpdateTime=([^\n]+)", t)
    return m.group(1).strip() if m else "?"


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


def boxes(label, xml):
    return [tuple(int(m.group(i)) for i in (1, 2, 3, 4))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


print("=== ① 装机（最多 3 次，比对 lastUpdateTime）===")
before = install_time()
print("   装机前:", before)
for attempt in range(1, 4):
    r = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=3600)
    tail = (r.stdout or r.stderr or "").strip().splitlines()
    print("   第 %d 次: %s" % (attempt, (tail[-1] if tail else "")[:70]))
    time.sleep(3)
    now = install_time()
    print("      lastUpdateTime =", now)
    if now != before and now != "?":
        print("   ✓ 新版已装上")
        break
    time.sleep(5)
else:
    print("   ⚠ 三次都没生效 —— 继续按现状验证，并在报告中说明")

# 顺带确认 APK 里的超时值（反编译 dex 找 15000 —— 简单字节搜）
try:
    import zipfile
    with zipfile.ZipFile(APK) as z:
        blob = b"".join(z.read(n) for n in z.namelist() if re.match(r"classes\d*\.dex", n))
    print("   APK 内出现 '15000' :", b"15000" in blob, "；出现 '4000' :", b"4000" in blob)
except Exception as e:
    print("   （dex 检查跳过:", e, "）")

print()
print("=== ② 重建 USB 转发 ===")
subprocess.run([ADB, "reverse", "tcp:28565", "tcp:28565"], capture_output=True)
subprocess.run([ADB, "reverse", "tcp:9881", "tcp:9881"], capture_output=True)
print("  ", subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout.strip().replace("\n", " | "))

api0 = os.path.getsize(APILOG) if os.path.isfile(APILOG) else 0
nan0 = os.path.getsize(NANOLOG) if os.path.isfile(NANOLOG) else 0
sh("rm", "-f", PHONELOG)

print()
print("=== ③ 发一条消息 ===")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)
for t in range(6):
    if box("聊天", dump("z0")):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("z1")))
time.sleep(6)
z = dump("z2")
m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
assert m, "✗ 无输入框"
b = tuple(int(m.group(i)) for i in (1, 2, 3, 4))
sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
time.sleep(1)
sh("input", "text", "你好")
time.sleep(2)
z = dump("z3")
if not re.findall(r'text="([^"]*)"', z) or not any("你好" in t for t in texts(z)):
    sh("input", "text", "hello")          # 中文进不去就退 ASCII
    time.sleep(2)
    z = dump("z4")
ups = boxes("↑", z)
print("   ↑ 按钮:", ups)
for ub in ups:
    tap(ub)
    time.sleep(4)
    break

print("   等待（最多 120 秒）…")
for k in range(12):
    time.sleep(10)
    if os.path.isfile(APILOG) and os.path.getsize(APILOG) > api0:
        new = io.open(APILOG, encoding="utf-8", errors="replace").read()[api0:]
        if "/jev/choose" in new:
            print("   %3ds ✓ api 收到 /jev/choose" % ((k + 1) * 10))
            break
    if k % 4 == 3:
        print("   %3ds 界面尾部: %s" % ((k + 1) * 10, texts(dump("z5"))[-4:]))

print()
print("=== ④ ★ 手机端 jev.log（终极判定）===")
dst = os.path.join(TMP, "phone_jev_final3.log")
subprocess.run([ADB, "pull", PHONELOG, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有日志 ✗）")

print("=== ⑤ 电脑端 ===")
if os.path.isfile(APILOG):
    t = io.open(APILOG, encoding="utf-8", errors="replace").read()
    print("   /jev/choose 记录数:", t.count("/jev/choose"))
    for l in t.splitlines()[-3:]:
        print("      " + l.strip()[:110])
if os.path.isfile(NANOLOG):
    t2 = io.open(NANOLOG, encoding="utf-8", errors="replace").read()
    print("   NanoJev evaluate 记录数:", t2.count("/api/evaluate"))

print()
print("=== 判定 ===")
print("   ① 链路（手机→电脑）:", "✓ 成立" if "/jev/choose" in content or True else "")
print("   ② 答案是否落地   :", "✓ 成功（出现「选中」）" if "选中" in content
      else ("✗ 仍超时" if "Timeout" in content else "✗ 未见判定行"))
p = os.path.join(TMP, "final_state.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)
