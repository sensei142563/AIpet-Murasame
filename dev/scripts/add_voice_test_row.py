# -*- coding: utf-8 -*-
"""设置页加「测试电脑语音」行（点一下调 VoiceClient.speak）→ 编译装机（核实）→ 自动点它 → pull voice.log。"""
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
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
VOICELOG = "/sdcard/Android/data/com.aipet.murasame/files/voice.log"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(SP, encoding="utf-8", newline="").read().splitlines(keepends=True)
print("=== 语音服务地址那一行的上下文 ===")
i = next((k for k, l in enumerate(L) if "语音服务地址" in l), None)
assert i is not None, "✗ 找不到语音服务地址行"
for k in range(max(0, i - 4), min(len(L), i + 8)):
    print("   %5d| %s" % (k + 1, L[k].rstrip()[:120]))

if "测试电脑语音" not in "".join(L):
    # 找到该 Row2 调用的结束（括号配平）
    d = 0
    j = i
    while j < len(L):
        d += L[j].count("(") - L[j].count(")")
        if d <= 0 and j > i:
            break
        j += 1
    eol = "\r\n" if L[j].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[i]).group(1)
    new = [
        eol,
        ind + "// [voice-test] 一键试听：直接调 VoiceClient 合成并播放（不经过聊天流程），" + eol,
        ind + "// 方便确认「手机 → 电脑 F5-TTS → 播放」这条链是否通；结果写 voice.log。" + eol,
        ind + 'Row2("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）",' + eol,
        ind + "    Icons.Default.PlayArrow, text, sub) {" + eol,
        ind + '    runCatching { VoiceClient.speak(_ctx, "你好，我是丛雨。", petId = "murasame") }' + eol,
        ind + '        .onFailure { notice = "测试失败：" + it.message }' + eol,
        ind + "}" + eol,
    ]
    L = L[:j + 1] + new + L[j + 1:]
    io.open(SP, "w", encoding="utf-8", newline="").write("".join(L))
    print("✓ 已插入「测试电脑语音」行（在第 %d 行之后）" % (j + 1))

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
    print("   第 %d 次:", ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:50])
    time.sleep(3)
    now = itime()
    print("      lastUpdateTime =", now)
    if now != before and now != "?":
        print("   ✓ 已装上")
        break

MSG = """feat(voice): 设置页加「测试电脑语音」一键试听行

朗读链路此前只能在聊天回复时触发，难以单独验证（朗读开关、聊天发送都牵扯进来）。
新增设置页行「测试电脑语音」：点一下直接调用 VoiceClient.speak(_ctx, "你好，我是丛雨。",
petId = "murasame")，走 手机 → 电脑 F5-TTS /infer → wav → MediaPlayer 播放，
并把过程写进 voice.log（外部可 pull）。失败时在设置页提示。

用途：① 用户可以一键试听丛雨音色是否正常；② 便于自动验收单独验证语音链路。
"""
msg = os.path.join(MAP, "_msg_voicetest.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                  capture_output=True, text=True).stdout.strip(), "条")
