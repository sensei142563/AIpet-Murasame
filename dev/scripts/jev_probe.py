# -*- coding: utf-8 -*-
"""加外部可读日志目录 + chatOnce 入口探针 → 编译装机 → 发一条 → pull 日志。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
JC = os.path.join(BASE, "bot/chat/JevClient.kt")
CC = os.path.join(BASE, "bot/chat/ChatCore.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ① JevClient.log 同时写外部目录（adb 可直接 pull）
s = io.open(JC, encoding="utf-8", newline="").read()
if "getExternalFilesDir" not in s:
    L = s.splitlines(keepends=True)
    i = next(k for k, l in enumerate(L) if "f.appendText(line" in l)
    eol = "\r\n" if L[i].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[i]).group(1)
    add = [
        ind + "// 同时写一份到外部目录：adb pull /sdcard/Android/data/<pkg>/files/jev.log 就能看到" + eol,
        ind + "runCatching {" + eol,
        ind + "    val ext = java.io.File(c.getExternalFilesDir(null) ?: return@runCatching, \"jev.log\")" + eol,
        ind + "    if (ext.isFile && ext.length() > 256 * 1024) ext.writeText(\"\")" + eol,
        ind + "    ext.appendText(line + \"\\n\")" + eol,
        ind + "}" + eol,
    ]
    L = L[:i + 1] + add + L[i + 1:]
    io.open(JC, "w", encoding="utf-8", newline="").write("".join(L))
    print("✓ JevClient：日志同时写外部目录")

# ② chatOnce 入口探针
s2 = io.open(CC, encoding="utf-8", newline="").read()
if "chatOnce 进入" not in s2:
    L2 = s2.splitlines(keepends=True)
    i2 = next(k for k, l in enumerate(L2) if "val stickersAvailable = if (useSticker)" in l)
    eol = "\r\n" if L2[i2].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L2[i2]).group(1)
    add = [
        ind + "// [probe] 探针：确认本轮回复确实走过这条路径，以及候选表情包有多少" + eol,
        ind + "JevClient.log(\"chatOnce 进入: useSticker=\" + useSticker + \" 候选=\" + stickersAvailable.size +" + eol,
        ind + "    \" baseUrl='\" + JevClient.baseUrl + \"'\")" + eol,
    ]
    L2 = L2[:i2 + 1] + add + L2[i2 + 1:]
    io.open(CC, "w", encoding="utf-8", newline="").write("".join(L2))
    print("✓ ChatCore：已加 chatOnce 入口探针（含 baseUrl 现值）")

print("=== 编译装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:140])
if r.returncode != 0:
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   装机:", (subprocess.run([ADB, "install", "-r", APK], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800).stdout or "").strip()[-16:])
# 清掉旧日志
subprocess.run([ADB, "shell", "run-as", "com.aipet.murasame", "true"], capture_output=True)
out = subprocess.run([ADB, "shell", "rm", "-f",
                      "/sdcard/Android/data/com.aipet.murasame/files/jev.log"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   清旧日志:", (out.stdout or out.stderr or "ok").strip()[:60])

MSG = """chore(jev): 日志加外部可读副本 + chatOnce 入口探针（定位 /jev/choose 从未发出的原因）

已确认 dex 里确实包含 JevClient/jev-choose/探针文本（即代码进了包），但真机上
api 日志无请求、logcat 也无输出，因此需要更硬的证据：
  - JevClient.log 除了私有 files/jev.log 与 logcat，再写一份到
    getExternalFilesDir()/jev.log —— 可用 adb pull /sdcard/Android/data/<pkg>/files/jev.log 直接读取；
  - ChatCore.chatOnce 在算出 stickersAvailable 后打一条探针，记录 useSticker、候选数量
    与 JevClient.baseUrl 的当前值，用来判断是"没走到这里"还是"baseUrl 为空"。

验证：编译装机后真机发一条消息，再 pull 该日志。
"""
msg = os.path.join(MAP, "_msg_jevprobe.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
