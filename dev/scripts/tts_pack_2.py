# -*- coding: utf-8 -*-
"""修 VoiceClient 第 132 行的 toString(Charset) 写法 → 编译装机 → 点设置页「测试电脑语音」验收
   （期望：voice.log 出现"命中预生成台词"，且 f5tts.log 零增长 = 没联网）。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = os.path.join(MAIN, "dev/shots")
LOGS = os.path.join(MAIN, "dev", "logs")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

s = io.open(VC, encoding="utf-8").read().replace("\r\n", "\n")
bad = '                JSONObject(ctx.assets.open("voice/index.json").use { it.readBytes().toString(Charsets.UTF_8)) }'
new = ('                JSONObject(ctx.assets.open("voice/index.json").use { ins ->\n'
       '                    ins.readBytes().toString(Charsets.UTF_8)\n'
       '                })')
if bad in s:
    s = s.replace(bad, new, 1)
    io.open(VC, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已修第 132 行")
else:
    print("· 未找到旧写法（可能已改）")

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:230])
if r.returncode != 0:
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\n]+)", t)
    return mm.group(1).strip() if mm else "?"


b = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   装 %d:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:44])
    time.sleep(3)
    now = itime()
    if now != b and now != "?":
        print("   ✓ 已装上:", now)
        break

NET = "192.168.43.1:5555"
devs = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=60).stdout
DEV = NET if NET in devs else None


def adb(*a, t=300):
    cmd = [ADB] + (["-s", DEV] if DEV else []) + list(a)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=t).stdout or ""


def dump(tag):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB] + (["-s", DEV] if DEV else []) + ["pull", "/sdcard/%s.xml" % tag,
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
    adb("shell", "input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    print("   tap %s" % tag)
    time.sleep(2.5)
    return True


f5p = os.path.join(LOGS, "f5tts.log")
f5_before = os.path.getsize(f5p) if os.path.isfile(f5p) else 0
print()
print("=== 验收：点「测试电脑语音」（这句已预生成为台词，应离线播放）===")
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "am", "force-stop", PKG)
time.sleep(3)
adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(15)
z = dump("t1")
tap(box("设置", z), "底部导航 设置")
time.sleep(5)
z = dump("t2")
tx = [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()]
print("   设置页含语音的项:", [t for t in tx if "语音" in t or "朗读" in t or "Jev" in t][:6])
if not box("测试电脑语音", z):
    # 可能在二级页：先找「语音」入口
    for lb in ("语音", "语音服务", "朗读"):
        if tap(box(lb, z), "进 " + lb):
            time.sleep(3)
            z = dump("t3")
            print("   二级页:", [t for t in re.findall(r'text="([^"]*)"', z) if t.strip()][:8])
            break
oktap = tap(box("测试电脑语音", z), "测试电脑语音")
time.sleep(16)
f5_after = os.path.getsize(f5p) if os.path.isfile(f5p) else 0
print("   f5tts.log: %d → %d" % (f5_before, f5_after))
vlog = adb("shell", "cat", "/sdcard/Android/data/%s/files/voice.log" % PKG)
lines = [l for l in vlog.splitlines() if l.strip()][-6:]
for l in lines:
    print("   voice | " + l.strip()[:140])
hit = any("命中预生成台词" in l for l in lines)
print()
print("   ✓ 台词包命中（离线播放）" if hit else "   ✗ 没看到台词包命中")
print("   ✓ 没有联网调用（f5tts.log 零增长）" if f5_after == f5_before else "   ⚠ f5tts.log 有增长（走了网络）")
