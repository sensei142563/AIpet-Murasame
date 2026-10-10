# -*- coding: utf-8 -*-
"""修 load() 没写回 baseUrl（Jev + Voice）→ 编译装机 → 发一条 → 两侧日志取证。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

for fn, label in (("bot/chat/JevClient.kt", "Jev"), ("bot/chat/VoiceClient.kt", "Voice")):
    p = os.path.join(BASE, fn)
    s = io.open(p, encoding="utf-8", newline="").read()
    if "baseUrl = v" in s or "baseUrl = value" in s:
        print("（%s 已修）" % label)
        continue
    L = s.splitlines(keepends=True)
    i = next((k for k, l in enumerate(L) if re.search(r"fun load\(ctx: Context\)", l)), None)
    if i is None:
        print("✗ %s 找不到 load()" % label)
        continue
    eol = "\r\n" if L[i].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[i]).group(1)
    # 把 "if (f.isFile) f.readText().trim() else ..." 改成先取到 v 再写回 baseUrl
    j = next((k for k in range(i, min(len(L), i + 8)) if "readText()" in L[k]), None)
    if j is None:
        print("✗ %s 找不到 readText" % label)
        continue
    ind2 = re.match(r"(\s*)", L[j]).group(1)
    L[j] = (ind2 + "val v = if (f.isFile) f.readText().trim() else \"\"" + eol +
            ind2 + "// ★ load() 必须写回静态字段，否则只是「读出来看看」——" + eol +
            ind2 + "// 设置页能显示地址，但运行期的 baseUrl 一直是空串（这正是 /jev/choose 发不出的真因）。" + eol +
            ind2 + "baseUrl = v" + eol +
            ind2 + "v" + eol)
    io.open(p, "w", encoding="utf-8", newline="").write("".join(L))
    print("✓ %s：load() 现在会写回 baseUrl" % label)
    for k in range(i, min(len(L), i + 10)):
        print("      %5d| %s" % (k + 1, L[k].rstrip()[:112]))

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
                    "app/src/main/java/com/aipet/murasame/bot/chat/JevClient.kt",
                    "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   装机:", (subprocess.run([ADB, "install", "-r", APK], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800).stdout or "").strip()[-16:])
subprocess.run([ADB, "shell", "rm", "-f", "/sdcard/Android/data/com.aipet.murasame/files/jev.log"],
               capture_output=True)

MSG = """fix(jev/voice): load() 没有写回 baseUrl —— 这才是 /jev/choose 从未发出的真因

排查链（每步都有实证）：
  1. 电脑端 api 日志从无 /jev/choose；手机 logcat 无输出 → 加外部可读日志 + chatOnce 探针
  2. pull 到手机日志，看到 chatOnce 进入: useSticker=true 候选=20 **baseUrl=''** → 地址在运行期是空串
  3. 设置页里填好并点保存后，地址能在 UI 上显示、也能跨冷启动显示（说明文件里有值），
     但探针依旧打印 baseUrl='' → 问题在代码：load() 只 return 读到的值，
     **从未写回静态字段 baseUrl**；设置页用 load() 的返回值渲染，所以"看起来是对的"。
  4. 修复：load() 里 val v = ...; baseUrl = v; v（JevClient 与 VoiceClient 都改）。

顺带（本轮早先）：App.onCreate 里补 JevClient.load/VoiceClient.load；Jev 日志同时写
getExternalFilesDir()/jev.log（adb pull 可直接取证）并接入 App 的 LogBus。

验证：编译装机后真机发一条消息，确认手机日志出现"请求 …/jev/choose"+ 选中项，且电脑端
api 日志出现 POST /jev/choose。
"""
msg = os.path.join(MAP, "_msg_loadfix.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
