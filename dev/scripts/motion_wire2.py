# -*- coding: utf-8 -*-
"""接线（补逗号版）：给 Live2DView 调用加 motionHint → 编译装机提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\_audit_fish9269\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(CS, encoding="utf-8", newline="").read().splitlines(keepends=True)
i = next(k for k, l in enumerate(L) if "Live2DView(" in l)
d = 0
j = i
while j < len(L):
    d += L[j].count("(") - L[j].count(")")
    if d <= 0 and j > i:
        break
    j += 1
eol = "\r\n" if L[j].endswith("\r\n") else "\n"
prev = L[j - 1].rstrip("\r\n")
if not prev.rstrip().endswith(","):
    L[j - 1] = prev.rstrip() + "," + eol
    print("✓ 给上一参数补逗号：%s" % L[j - 1].strip()[:100])
lead = re.match(r"(\s*)", L[j]).group(1)
L = L[:j] + [lead + "    motionHint = if (petId == \"murasame\") motionHintOf(ChatStore.emotion) else null," + eol] + L[j:]
io.open(CS, "w", encoding="utf-8", newline="").write("".join(L))
print("=== 调用处 ===")
for k in range(i, min(len(L), j + 3)):
    print("   %5d| %s" % (k + 1, L[k].rstrip()[:118]))

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
                    "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   装机:", (subprocess.run([ADB, "install", "-r", APK], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800).stdout or "").strip()[-16:])

MSG = """fix(live2d): 补上情绪→动作的调用点（含补逗号）

上一条只给 Live2DView 加了 motionHint 能力，聊天页的多行调用没接上，功能未生效。
本次按括号配平定位该调用，并给前一个参数补上尾逗号，再加入：
    motionHint = if (petId == "murasame") motionHintOf(ChatStore.emotion) else null,
（仅丛雨；诺瓦模型没有声明动作）

验证：assembleRelease 通过并装机。
"""
msg = os.path.join(MAP, "_msg_motionwire2.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
