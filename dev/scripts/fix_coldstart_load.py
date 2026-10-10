# -*- coding: utf-8 -*-
"""修复：App.onCreate 里加载 Jev/Voice 地址 + Jev 日志接 LogBus → 编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
APP = os.path.join(BASE, "App.kt")
JEVC = os.path.join(BASE, "bot/chat/JevClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ① App.kt：onCreate 里加载两个地址
s = io.open(APP, encoding="utf-8", newline="").read()
print("=== App.kt 现状 ===")
for i, l in enumerate(s.splitlines(), 1):
    print("   %5d| %s" % (i, l.rstrip()[:112]))
if "JevClient.load" not in s:
    L = s.splitlines(keepends=True)
    i = next(k for k, l in enumerate(L) if "override fun onCreate()" in l)
    j = i
    while j < len(L) and "super.onCreate()" not in L[j]:
        j += 1
    eol = "\r\n" if L[j].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[j]).group(1)
    add = [
        eol,
        ind + "// [fix] 冷启动就把电脑端地址读回内存 —— 之前只在设置页里 load()，" + eol,
        ind + "// 于是没进过设置页的进程里 JevClient.baseUrl 一直是空的，/jev/choose 一次都不会发。" + eol,
        ind + "runCatching { com.aipet.murasame.bot.chat.JevClient.load(this) }" + eol,
        ind + "runCatching { com.aipet.murasame.bot.chat.VoiceClient.load(this) }" + eol,
    ]
    L = L[:j + 1] + add + L[j + 1:]
    io.open(APP, "w", encoding="utf-8", newline="").write("".join(L))
    print("✓ App.kt：onCreate 里加了 JevClient.load / VoiceClient.load")

# ② JevClient.log：同时写 LogBus（App 内可见）
s2 = io.open(JEVC, encoding="utf-8", newline="").read()
if "LogBus" not in s2:
    L2 = s2.splitlines(keepends=True)
    i = next(k for k, l in enumerate(L2) if 'android.util.Log.i("JevClient"' in l)
    eol = "\r\n" if L2[i].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L2[i]).group(1)
    L2.insert(i + 1, ind + "runCatching { com.aipet.murasame.bot.LogBus.log(\"[Jev] \" + line) }" + eol)
    io.open(JEVC, "w", encoding="utf-8", newline="").write("".join(L2))
    print("✓ JevClient.log：已同时写入 LogBus（App 日志页可见）")

print("=== 编译装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/App.kt",
                    "app/src/main/java/com/aipet/murasame/bot/chat/JevClient.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   装机:", (subprocess.run([ADB, "install", "-r", APK], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800).stdout or "").strip()[-16:])

MSG = """fix(jev): 冷启动即加载电脑端地址（此前只在设置页 load，导致 /jev/choose 从不发出）

排查结论：JevClient.baseUrl / VoiceClient.baseUrl 只在 SettingsPage 里通过
JevClient.load()/VoiceClient.load() 赋值，因此**冷启动后若没进过设置页，baseUrl 一直是空串**，
choose() 在第一行 `if (base.isEmpty())` 就返回 —— 一个请求都不发，这就是"手机聊天有回复但
电脑端 api 日志里从没出现 /jev/choose"的原因。

修复：
  App.onCreate() 里 runCatching { JevClient.load(this); VoiceClient.load(this) }
另外把 Jev 的日志同时写入 App 自己的 LogBus（之前只写 logcat 与私有文件，
release 版无法 run-as 读取，用户在 App 里也看不到）。

验证：assembleRelease 通过并装机；随后用真机发一条消息，确认电脑端 api 日志出现 /jev/choose。
"""
msg = os.path.join(MAP, "_msg_coldstart.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
