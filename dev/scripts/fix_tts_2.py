# -*- coding: utf-8 -*-
"""① ⑤b 检查：先选「离线音色」，再点「点一下测试」触发真实合成
   ② 编译装机
   ③ 真机走一遍并读 live2d.log 的 [tts] 行 —— 判断真实离线 TTS 到底行不行"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 修 ⑤b 检查 ----------
a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                  if tap_text_any(dump("b5"), ["离线音色"]):
                      time.sleep(12)
                      lg = read_log("live2d.log")
                      lines = [l for l in (lg or "").splitlines() if "[tts]" in l]
                      record("⑤b 离线 TTS 合成", verdict(any("ready" in l or "返回" in l for l in lines)), (lines[-1:] or ["(无 [tts] 日志)"])[0].strip()[:110])
                  else:
                      record("⑤b 离线 TTS 合成", "SKIP", "设置页没找到「离线音色」")'''
new = '''                  # 「离线音色」只是**音色选择**，真正触发合成的是下面的「点一下测试」。
                  # 之前只点了音色选择，所以日志里根本没有真实合成记录，判 FAIL 属于检查项写错。
                  sel = tap_text_any(dump("b5"), ["离线音色"])
                  trig = tap_text_any(dump("b6"), ["点一下测试"])
                  if not (sel or trig):
                      record("⑤b 离线 TTS 合成", "SKIP", "设置页没找到「离线音色」/「点一下测试」")
                  else:
                      time.sleep(15)
                      lg = read_log("live2d.log")
                      lines = [l for l in (lg or "").splitlines() if "[tts]" in l]
                      ok = any(("ready lang" in l) or ("samples=" in l) for l in lines)
                      bad = [l for l in lines if "failed" in l]
                      if ok:
                          record("⑤b 离线 TTS 合成", "PASS",
                                 [l for l in lines if "samples=" in l][-1:][0].strip()[:120]
                                 if any("samples=" in l for l in lines)
                                 else [l for l in lines if "ready lang" in l][-1].strip()[:120])
                      elif bad:
                          record("⑤b 离线 TTS 合成", "FAIL", bad[-1].strip()[:130])
                      else:
                          record("⑤b 离线 TTS 合成", "FAIL",
                                 "点了测试但 [tts] 没有 ready/samples 行："
                                 + ((lines[-1:] or ["(无 [tts] 日志)"])[0].strip()[:110]))'''
if old in a:
    a = a.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(a)
    print("✓ ① ⑤b 检查已改为「选音色 + 点一下测试」，并细分 PASS/FAIL 依据")
else:
    print("✗ ① ⑤b 锚点未命中")

print()
print("=== ② 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")


def adb(*x, timeout=240):
    rr = subprocess.run([ADB, "-s", DEV, *x], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=timeout)
    return (rr.stdout or "") + (rr.stderr or "")


def dump(name):
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % name)
    adb("pull", "/sdcard/%s.xml" % name, os.path.join(SD, "%s.xml" % name))
    p = os.path.join(SD, "%s.xml" % name)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def tap(x, needle, wait=3.0, scroll=0):
    for _ in range(max(1, scroll)):
        ns = []
        for m in re.finditer(r'<node(?P<a1>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<a2>[^>]*?)/?>', x):
            at = (m.group("a1") or "") + (m.group("a2") or "")
            tm = re.search(r'text="([^"]*)"', at)
            ns.append({"t": tm.group(1) if tm else "", "c": 'clickable="true"' in at,
                       "x1": int(m.group("x1")), "y1": int(m.group("y1")),
                       "x2": int(m.group("x2")), "y2": int(m.group("y2"))})
        for i, nd in enumerate(ns):
            if needle in nd["t"]:
                tx, ty = (nd["x1"] + nd["x2"]) // 2, (nd["y1"] + nd["y2"]) // 2
                tgt = None
                for j in range(i - 1, -1, -1):
                    c = ns[j]
                    if c["c"] and c["x1"] <= tx <= c["x2"] and c["y1"] <= ty <= c["y2"]:
                        tgt = c
                        break
                tgt = tgt or nd
                cx, cy = (tgt["x1"] + tgt["x2"]) // 2, (tgt["y1"] + tgt["y2"]) // 2
                adb("shell", "input", "tap", str(cx), str(cy))
                time.sleep(wait)
                return (cx, cy)
        adb("shell", "input", "swipe", "612", "1900", "612", "1000", "250")
        time.sleep(1.2)
        x = dump("sc")
    return None


print()
print("=== ③ 真机触发真实离线合成 ===")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
print("   点聊天:", tap(dump("c1"), "聊天", 4.0))
print("   点☰:", tap(dump("c2"), "☰", 3.0))
print("   点设置:", tap(dump("c3"), "设置", 4.0))
print("   选离线音色:", tap(dump("c4"), "离线音色", 2.0))
print("   点一下测试:", tap(dump("c5"), "点一下测试", 20.0))
print()
print("=== live2d.log 里的 [tts] 行 ===")
log = adb("shell", "cat", EXT + "/live2d.log")
for l in [l for l in (log or "").splitlines() if "[tts]" in l][-14:]:
    print("   " + l.strip()[:170])
