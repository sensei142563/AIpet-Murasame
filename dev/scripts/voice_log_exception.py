# -*- coding: utf-8 -*-
"""在 speak() 的 runCatching 里记录异常（getOrElse + log）→ 编译装机 → 点测试 → pull voice.log。"""
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
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
VL = "/sdcard/Android/data/com.aipet.murasame/files/voice.log"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
print("=== speak() 里的 runCatching / getOrDefault ===")
for i, l in enumerate(L, 1):
    if re.search(r"(val ok = runCatching|getOrDefault|\.getOrNull\(\)|runCatching \{)", l):
        print("   %5d| %s" % (i, l.strip()[:118]))
# 把 "val ok = runCatching {" 那段结尾的 getOrDefault(false) 换成 getOrElse { log(...); false }
pat = re.compile(r"(\s*)\.getOrDefault\(false\)")
hit = None
for k, l in enumerate(L):
    if pat.match(l) and any("val ok = runCatching" in L[x] for x in range(max(0, k - 40), k)):
        hit = k
        break
if hit is not None:
    eol = "\r\n" if L[hit].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[hit]).group(1)
    L[hit] = (ind + ".getOrElse { e ->" + eol +
              ind + "    log(\"异常：\" + e.javaClass.simpleName + \" \" + e.message)" + eol +
              ind + "    false" + eol +
              ind + "}" + eol)
    io.open(VC, "w", encoding="utf-8", newline="").write("".join(L))
    print("✓ 已把第 %d 行的 getOrDefault(false) 换成记录异常" % (hit + 1))
else:
    print("⚠ 没找到可替换处（打印更多上下文）")
    for i, l in enumerate(L, 1):
        if 95 <= i <= 140:
            print("   %5d| %s" % (i, l.rstrip()[:118]))

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
    t = subprocess.run([ADB, "shell", "dumpsys", "package", "com.aipet.murasame"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    m = re.search(r"lastUpdateTime=([^\n]+)", t)
    return m.group(1).strip() if m else "?"


before = itime()
print("   装机前:", before)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   第 %d 次:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:50])
    time.sleep(3)
    now = itime()
    print("      lastUpdateTime =", now)
    if now != before and now != "?":
        print("   ✓ 已装上")
        break

MSG = """chore(voice): speak() 记录异常详情（此前异常被 runCatching 吞掉，只看到"合成/落盘失败"）

真机测试发现点「测试电脑语音」时 base 正常（base='http://127.0.0.1:9881'）却没有 F5 请求，
说明请求阶段抛了异常但被静默吞掉。本次把 runCatching 的 getOrDefault(false) 换成
getOrElse { e -> log("异常：" + e.javaClass.simpleName + " " + e.message); false }，
让 voice.log 直接写出异常类型与消息（例如 ConnectException / CLEARTEXT / SocketTimeout）。
"""
msg = os.path.join(MAP, "_msg_voiceexc.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                  capture_output=True, text=True).stdout.strip(), "条")
