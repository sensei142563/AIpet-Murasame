# -*- coding: utf-8 -*-
"""块内 return false → return@runCatching false（仅限合成块行区间）→ 编译装机 → 点测试 → 日志。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
VL = "/sdcard/Android/data/%s/files/voice.log" % PKG
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
# 找合成块区间：从 val ok = runBlocking 到含 getOrElse 的那一行
i = next(k for k, l in enumerate(L) if "val ok = kotlinx.coroutines.runBlocking {" in l)
j = next(k for k in range(i, len(L)) if ".getOrElse { e -> log(" in L[k])
n = 0
for k in range(i, j + 1):
    if re.search(r"\breturn false\b", L[k]):
        L[k] = re.sub(r"\breturn false\b", "return@runCatching false", L[k])
        n += 1
print("✓ 区间 %d~%d 内替换 return false → return@runCatching false：%d 处" % (i + 1, j + 1, n))
io.open(VC, "w", encoding="utf-8", newline="").write("".join(L))

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:6]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    m = re.search(r"lastUpdateTime=([^\n]+)", t)
    return m.group(1).strip() if m else "?"


before = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   装 %d:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:44])
    time.sleep(3)
    now = itime()
    if now != before and now != "?":
        print("   ✓ 已装上:", now)
        break


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


subprocess.run([ADB, "reverse", "tcp:28565", "tcp:28565"], capture_output=True)
subprocess.run([ADB, "reverse", "tcp:9881", "tcp:9881"], capture_output=True)
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("z0")))
time.sleep(5)
tap(box("☰", dump("z1")))
time.sleep(3)
z = dump("z2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
z = dump("z3")
row = box("测试电脑语音", z)
print("   行:", row)
sh("rm", "-f", VL)
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
tap(row)
for k in range(7):
    time.sleep(8)
    if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
        if "/infer" in io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]:
            print("   ✓ F5 收到 /infer（%ds）" % ((k + 1) * 8))
            break
    print("   %ds …" % ((k + 1) * 8))
print()
print("=== ★ voice.log ===")
dst = os.path.join(TMP, "phone_voice10.log")
subprocess.run([ADB, "pull", VL, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有 ✗）")
print("=== 判定 ===")
print("   ✅✅✅✅ TTS 成功！" if "成功播放" in content else
      ("   ⚠ 仍异常 → " + str([l for l in content.splitlines() if "异常" in l][:1]) if "异常" in content else "   ? 见日志"))

MSG = """fix(voice): 合成块内的 return false 改为 return@runCatching false（withContext 里禁止 return）

把整个合成块包进 withContext(Dispatchers.IO) 后，块内原有的裸 return false 触发
"'return' is prohibited"。改为 return@runCatching false（仅限该块区间，外层 !ok 的 return 不动）。
"""
msg = os.path.join(MAP, "_msg_netmainthread3.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:100])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
