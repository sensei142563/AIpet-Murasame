# -*- coding: utf-8 -*-
"""找到电脑后，一键把两处地址填好（语音 F5 :9881 / Jev api :28565），并如实显示填了什么。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

s = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                netLine = base + "｜" + (host?.let { "找到电脑：$it（api.py 28565 有响应）" }'''
new = '''                if (host != null) {
                    // 找到就一键填好两处地址（语音 F5 :9881、Jev api :28565）。
                    // 地址是同一台电脑上的两个服务，所以主机名相同、端口不同。
                    runCatching {
                        VoiceClient.save(vctx, "http://" + host + ":9881")
                        JevClient.save(vctx, "http://" + host + ":28565")
                        voiceAddr = "http://" + host + ":9881"
                    }
                }
                netLine = base + "｜" + (host?.let {
                    "找到电脑：$it ⇒ **已自动填入** 语音 http://$it:9881 与 Jev http://$it:28565" }'''
if old in s:
    s = s.replace(old, new, 1)
    io.open(SP, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已加：找到电脑后一键填入两处地址")
else:
    print("⚠ 锚点未命中")

print()
print("=== 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")
