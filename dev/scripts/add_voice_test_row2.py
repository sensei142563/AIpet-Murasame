# -*- coding: utf-8 -*-
"""锚到真正的 Row2("语音服务地址" 行 → 插入「测试电脑语音」（只用已有变量/图标）→ 编译装机。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(SP, encoding="utf-8", newline="").read().splitlines(keepends=True)
i = next((k for k, l in enumerate(L) if re.search(r'Row2\(\s*"语音服务地址"', l)), None)
assert i is not None, "✗ 找不到 Row2(\"语音服务地址\")"
print("=== 锚点（第 %d 行）及其后 ===" % (i + 1))
for k in range(i, min(len(L), i + 6)):
    print("   %5d| %s" % (k + 1, L[k].rstrip()[:118]))
# 括号配平找该 Row2 调用结束
d = 0
j = i
while j < len(L):
    d += L[j].count("(") - L[j].count(")")
    if d <= 0 and j > i:
        break
    j += 1
print("   该调用结束于第 %d 行: %s" % (j + 1, L[j].rstrip()[:80]))

if "测试电脑语音" not in "".join(L):
    eol = "\r\n" if L[j].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[i]).group(1)
    new = [
        eol,
        ind + "// [voice-test] 一键试听：直接调 VoiceClient（不经过聊天流程），便于验证语音链路" + eol,
        ind + 'Row2("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）",' + eol,
        ind + "    Icons.Default.VolumeUp, text, sub) {" + eol,
        ind + '    runCatching { VoiceClient.speak(vctx, "你好，我是丛雨。", petId = "murasame") }' + eol,
        ind + "}" + eol,
    ]
    L = L[:j + 1] + new + L[j + 1:]
    io.open(SP, "w", encoding="utf-8", newline="").write("".join(L))
    print("✓ 已在第 %d 行之后插入「测试电脑语音」" % (j + 1))

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt"], capture_output=True)
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

MSG = """feat(voice): 设置页加「测试电脑语音」一键试听（修正插入位置后）

第一次插入锚到了注释里的"语音服务地址"，落进 Card2 开头导致编译失败（PlayArrow/_ctx/notice
都不可见），已回滚。本次锚定真正的 Row2("语音服务地址") 行并按其括号配平插入到该行之后，
只用当前作用域已有变量 vctx 与已导入的 Icons.Default.VolumeUp。

用途：点一下即调 VoiceClient.speak(vctx, "你好，我是丛雨。", petId = "murasame")，
走 手机 → 电脑 F5-TTS /infer → wav → MediaPlayer，全过程写 voice.log（外部可 pull）。
"""
msg = os.path.join(MAP, "_msg_voicetest2.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                  capture_output=True, text=True).stdout.strip(), "条")
