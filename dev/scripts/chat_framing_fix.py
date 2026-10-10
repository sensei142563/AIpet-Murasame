# -*- coding: utf-8 -*-
"""修聊天页 Live2D 头顶出框：给它的 Modifier 加 graphicsLayer（缩放 0.9 + 下移）→ 编译装机提交。"""
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
# 该调用的第一个参数行（下一行）
arg_line = i + 1
print("=== 现在（%d~%d）===" % (i + 1, min(len(L), i + 5)))
for k in range(i, min(len(L), i + 5)):
    print("   %5d| %s" % (k + 1, L[k].rstrip()[:118]))

old = L[arg_line]
if "graphicsLayer" not in old:
    eol = "\r\n" if old.endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", old).group(1)
    L[arg_line] = (ind + "Modifier.fillMaxSize()" + eol +
                   ind + "    // 聊天页 Live2D 取景：略缩小并下移，避免头顶被裁（AR 页另有自己的取景）" + eol +
                   ind + "    .graphicsLayer(scaleX = 0.92f, scaleY = 0.92f, translationY = 70f)," + eol)
    io.open(CS, "w", encoding="utf-8", newline="").write("".join(L))
    print("=== 改后 ===")
    for k in range(i, min(len(L), i + 6)):
        print("   %5d| %s" % (k + 1, L[k].rstrip()[:118]))
else:
    print("（已有 graphicsLayer）")

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

MSG = """fix(chat-ui): 修聊天页 Live2D 头顶被裁（缩放 0.92 + 下移 70）

用户反馈：头顶出框的是**聊天页**的 Live2D（不是 AR 页 —— AR 页的取景上一条已单独调整）。
本处在聊天页的 Live2DView 第一个参数上加 graphicsLayer：
    scaleX/scaleY = 0.92，translationY = 70
只影响聊天页这一处；AR 页仍用自己的 scale=0.85 / dy=90 初始取景。

验证：assembleRelease 通过并装机。
"""
msg = os.path.join(MAP, "_msg_chatframing.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
