# -*- coding: utf-8 -*-
"""最后一步：JevClient 读超时 4s → 15s → 编译装机 → 重建转发 → 发消息 → 拉日志判定。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
JC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/JevClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

s = io.open(JC, encoding="utf-8", newline="").read()
print("=== 改前超时 ===")
for i, l in enumerate(s.splitlines(), 1):
    if "Timeout(" in l:
        print("   %5d| %s" % (i, l.strip()[:110]))
s2 = s.replace(".readTimeout(4000, TimeUnit.MILLISECONDS)", ".readTimeout(15000, TimeUnit.MILLISECONDS)")
s2 = s2.replace(".connectTimeout(1500, TimeUnit.MILLISECONDS)", ".connectTimeout(2500, TimeUnit.MILLISECONDS)")
io.open(JC, "w", encoding="utf-8", newline="").write(s2)
print("=== 改后 ===")
for i, l in enumerate(s2.splitlines(), 1):
    if "Timeout(" in l:
        print("   %5d| %s" % (i, l.strip()[:110]))
# 默认超时参数也一起放大
s3 = io.open(JC, encoding="utf-8", newline="").read().replace("timeoutMs: Int = 4000", "timeoutMs: Int = 15000")
io.open(JC, "w", encoding="utf-8", newline="").write(s3)
print("   默认 timeoutMs → 15000:", "timeoutMs: Int = 15000" in s3)

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
if r.returncode != 0:
    for y in [x for x in o.splitlines() if x.startswith("e: ")][:6]:
        print("   " + y[:130])
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/bot/chat/JevClient.kt"], capture_output=True)
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=3600)
print("   安装:", (rr.stdout or rr.stderr or "").strip().splitlines()[-1][:50])
subprocess.run([ADB, "reverse", "tcp:28565", "tcp:28565"], capture_output=True)
subprocess.run([ADB, "reverse", "tcp:9881", "tcp:9881"], capture_output=True)
print("   转发:", subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace").stdout.strip().replace("\n", " | "))
subprocess.run([ADB, "shell", "rm", "-f", "/sdcard/Android/data/com.aipet.murasame/files/jev.log"],
               capture_output=True)

MSG = """fix(jev): 放宽 Jev 客户端超时（读 4s→15s，连 1.5s→2.5s）

手机端日志显示请求确实发到了电脑（api 侧记录 POST /jev/choose 200 OK），
但客户端 4 秒就 SocketTimeoutException 放弃 —— 本地 NanoJev 首次推理 + 首次
HTTP 建连在真机上会超过 4 秒。放宽为读 15 秒、连 2.5 秒，让答案能真正落地。

（配合上一提交的 network_security_config 明文放行，与 USB 反向转发 adb reverse。）
"""
msg = os.path.join(MAP, "_msg_timeout.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
