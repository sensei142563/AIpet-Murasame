# -*- coding: utf-8 -*-
"""修 RIFF 判断（并删掉原 if 遗留的孤立 }）→ 编译 → 装机 → 提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\_audit_fish9269\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
i = next((k for k, l in enumerate(L) if "bytes[0]" in l and "'R'" in l), None)
assert i is not None, "✗ 找不到 RIFF 判断"
eol = "\r\n" if L[i].endswith("\r\n") else "\n"
ind = re.match(r"(\s*)", L[i]).group(1)
# 原结构：if (...) {\n  return false\n}   → 找到那个只含 } 的行并一起删
j = i
while j < len(L) and "return false" not in L[j]:
    j += 1
k = j + 1
while k < len(L) and L[k].strip() == "":
    k += 1
has_orphan = k < len(L) and L[k].strip() == "}"
print("   孤立 } 位于第 %d 行：%s" % (k + 1, has_orphan))
new = [
    ind + "// 必须是 WAV（以 RIFF 开头）才采用；否则视为失败并回退系统 TTS" + eol,
    ind + "val isRiff = bytes.size > 12 && bytes[0] == 'R'.code.toByte() &&" + eol,
    ind + "    bytes[1] == 'I'.code.toByte() && bytes[2] == 'F'.code.toByte() &&" + eol,
    ind + "    bytes[3] == 'F'.code.toByte()" + eol,
    ind + "if (!isRiff) return false" + eol,
]
end = k if has_orphan else j
L = L[:i] + new + L[end + 1:]
io.open(VC, "w", encoding="utf-8", newline="").write("".join(L))
print("=== 修复后（%d~%d）===" % (max(1, i - 3), i + 8))
for x in range(max(0, i - 3), min(len(L), i + 8)):
    print("   %5d| %s" % (x + 1, L[x].rstrip()[:116]))

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
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   装机:", (subprocess.run([ADB, "install", "-r", APK], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800).stdout or "").strip()[-16:])

MSG = """fix(voice/phone): 修 VoiceClient 里写反的 RIFF 判断（正确 WAV 被当成失败）

症状：聊天朗读听起来仍是系统 TTS，且鼻音重（鼻音来自 App 给系统 TTS 设的情绪音高/语速）。
根因：VoiceClient.speak 判断响应是否为音频时写反了：

    if (bytes[0] == 'R' && bytes[1] == 'I') { return false }   // 注释写的是「RIFF 才当音频」

电脑 F5 合成成功返回的 WAV 正好以 RIFF 开头，于是被判为失败，一次都没用上，全部回退系统 TTS。

改法：改为「不是 RIFF 才失败」：
    val isRiff = bytes.size > 12 && R && I && F && F
    if (!isRiff) return false
（同时删掉原 if 语句遗留的孤立右花括号）

验证：assembleRelease 通过并装机。
"""
msg = os.path.join(MAP, "_msg_riff2.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
