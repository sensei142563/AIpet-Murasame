# -*- coding: utf-8 -*-
"""修热点脚本的网关解析（改用 helper --gateway，不再走 PowerShell 引号地狱）→ 立刻用无线 adb 打通
   → 用设置页「测试电脑语音」做端到端验证（看 dev/logs/f5tts.log 是否新增 POST /infer）。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
HELPER = os.path.join(MAIN, "dev/scripts/hotspot_ready.py")
BAT = os.path.join(MAIN, "dev/热点连接.bat")
PKG = "com.aipet.murasame"
TMP = os.path.join(MAIN, "dev/shots")
LOG = os.path.join(MAIN, "dev/logs/f5tts.log")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ① helper 支持 --gateway（只打印网关）
h = io.open(HELPER, encoding="utf-8").read()
if "--gateway" not in h:
    h = h.replace('''if __name__ == "__main__":
    main()''', '''if __name__ == "__main__":
    if "--gateway" in sys.argv:
        print(default_gateway() or "")
    else:
        main()''', 1)
    io.open(HELPER, "w", encoding="utf-8", newline="\n").write(h)
    print("✓ hotspot_ready.py 支持 --gateway")

# ② bat 用 --gateway，不再用 PowerShell
b = io.open(BAT, encoding="gbk").read()
old = 'for /f "tokens=1" %%g in (\'powershell -NoProfile -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 ^| Sort-Object RouteMetric ^| Select-Object -First 1).NextHop"\') do set GW=%%g'
new = 'for /f "usebackq tokens=1" %%g in (`"%PY%" "%REPO%\\dev\\scripts\\hotspot_ready.py" --gateway`) do set GW=%%g'
if old in b:
    b = b.replace(old, new, 1)
    io.open(BAT, "w", encoding="gbk", newline="").write(b.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("✓ 热点连接.bat 改用 hotspot_ready.py --gateway")
else:
    print("· bat 里没找到旧网关行（可能已改）")

print()
print("=== 用修好的方式取网关 ===")
r = subprocess.run([PY, "-u", HELPER, "--gateway"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=300, cwd=MAIN)
gw = (r.stdout or "").strip().splitlines()
gw = gw[0].strip() if gw else ""
print("   网关（=手机热点地址）:", gw or "(空)")
note("取到网关", bool(re.match(r"^\d+\.\d+\.\d+\.\d+$", gw)))

print()
print("=== 无线 adb：connect + reverse（走热点，不用 USB）===")
subprocess.run([ADB, "connect", "%s:5555" % gw], capture_output=True, timeout=180)
devs = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=120).stdout
print("   设备列表:", devs.replace("\n", " ").strip()[:160])
note("无线 adb 已连上", ("%s:5555" % gw) in devs and "device" in devs)
for p in (28565, 9881):
    rr = subprocess.run([ADB, "-s", "%s:5555" % gw, "reverse", "tcp:%d" % p, "tcp:%d" % p],
                        capture_output=True, text=True, timeout=180)
    print("   reverse %d:" % p, ((rr.stdout or "") + (rr.stderr or "")).strip()[:60] or "ok")
lst = subprocess.run([ADB, "-s", "%s:5555" % gw, "reverse", "--list"], capture_output=True,
                     text=True, timeout=120).stdout
print("   无线通道转发列表:", lst.replace("\n", " | ").strip())
note("无线通道已建立两条转发", "28565" in lst and "9881" in lst)

print()
print("=== 端到端：点设置页「测试电脑语音」，看她是否出声（= 走通热点）===")
before = os.path.getsize(LOG) if os.path.isfile(LOG) else 0
print("   f5tts.log 之前大小:", before)


def sh(*a, t=300):
    return subprocess.run([ADB, "-s", "%s:5555" % gw, "shell", *a], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t).stdout or ""


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "-s", "%s:5555" % gw, "pull", "/sdcard/%s.xml" % tag,
                    os.path.join(TMP, "%s.xml" % tag)], capture_output=True, timeout=90)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))) if m else None


def tap(b, tag=""):
    if not b:
        print("   ✗ 没找到 %s" % tag)
        return False
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    print("   tap %s" % tag)
    time.sleep(2.5)
    return True


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
z = dump("h1")
tap(box("设置", z), "底部导航 设置")
time.sleep(5)
z = dump("h2")
tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
print("   设置页含测试:", [t for t in tx if "测试" in t][:3])
done = False
for lb in ("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）", "朗读"):
    if lb == "朗读":
        continue
    if tap(box(lb, z), lb):
        done = True
        break
time.sleep(14)
after = os.path.getsize(LOG) if os.path.isfile(LOG) else 0
print("   f5tts.log 之后大小:", after)
tail = ""
if os.path.isfile(LOG):
    tail = io.open(LOG, encoding="utf-8", errors="replace").read()[-1200:]
hits = [l for l in tail.splitlines() if "POST /infer" in l or "合成完成" in l]
print("   日志尾部相关行:")
for l in hits[-4:]:
    print("      " + l.strip()[:140])
note("F5 收到并完成了合成（= 热点链路端到端通）", after > before and any("POST /infer" in l for l in hits))
