# -*- coding: utf-8 -*-
"""修 VoiceClient：异常改由 getOrElse 记录；删掉判断之前那几条误导日志 → 编译装机 → 点测试 → pull 日志。"""
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
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
# ① 删掉判断之前的误导日志（按精确内容匹配）
drop_patterns = [
    r'^\s*log\("HTTP 失败 code=" \+ resp\.code\)\s*$',
    r'^\s*log\("响应体为空"\)\s*$',
    r'^\s*log\("响应太小 size=" \+ bytes\.size \+ " 内容=" \+ String\(bytes\)\.take\(120\)\)\s*$',
    r'^\s*log\("不是 RIFF size=" \+ bytes\.size \+ " 头=" \+ String\(bytes\)\.take\(16\)\)\s*$',
    r'^\s*log\("跳过：base=\'" \+ baseUrl \+ "\' 文本长=" \+ text\.length\)\s*$',
]
kept = []
removed = 0
for l in L:
    if any(re.match(p, l.rstrip("\r\n")) for p in drop_patterns):
        removed += 1
        continue
    kept.append(l)
L = kept
print("✓ 删除误导日志 %d 行" % removed)

# ② 合成块的 .getOrDefault(false) → 记录异常
pat = re.compile(r"^(\s*)\.getOrDefault\(false\)(\s*)$")
done = False
for k, l in enumerate(L):
    if pat.match(l.rstrip("\r\n")) and any("val ok = runCatching" in L[x] for x in range(max(0, k - 30), k)):
        eol = "\r\n" if l.endswith("\r\n") else "\n"
        ind = re.match(r"(\s*)", l).group(1)
        L[k] = (ind + ".getOrElse { e ->" + eol +
                ind + "    log(\"异常：\" + e.javaClass.simpleName + \" / \" + e.message)" + eol +
                ind + "    false" + eol +
                ind + "}" + eol)
        print("✓ 第 %d 行改为记录异常" % (k + 1))
        done = True
        break
if not done:
    print("✗ 仍未找到（打印 100~130 行）")
    for i, l in enumerate(L, 1):
        if 100 <= i <= 130:
            print("   %5d| %s" % (i, l.rstrip()[:118]))

# ③ "合成/落盘失败" 改成只在失败时打印
for k, l in enumerate(L):
    if re.match(r'^\s*log\("合成/落盘失败"\)\s*$', l.rstrip("\r\n")):
        eol = "\r\n" if l.endswith("\r\n") else "\n"
        ind = re.match(r"(\s*)", l).group(1)
        L[k] = ind + 'if (!ok) log("合成/落盘失败（原因见上面异常）")' + eol
        print("✓ 第 %d 行改为条件打印" % (k + 1))
io.open(VC, "w", encoding="utf-8", newline="").write("".join(L))

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

MSG = """fix(voice): speak() 记录异常详情；删除判断之前会误导的日志

上一轮真机实测：base 与文本都正常，但 F5 没收到请求、只看到"合成/落盘失败" —— 异常被
`.getOrDefault(false)` 静默吞掉（我上一轮想改它，正则没匹配到第 123 行，导致那次编译空转）。

本次按精确匹配处理：
  - `.getOrDefault(false)` → `.getOrElse { e -> log("异常：" + e.javaClass.simpleName + " / " + e.message); false }`
  - 删除我先前插在判断**之前**的 5 条日志（"HTTP 失败/响应体为空/响应太小/不是 RIFF/跳过"）——
    它们无条件打印，会误导排查
  - "合成/落盘失败" 改为仅在 !ok 时打印
"""
msg = os.path.join(MAP, "_msg_voiceexc2.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                  capture_output=True, text=True).stdout.strip(), "条")
