# -*- coding: utf-8 -*-
"""给 VoiceClient 每个失败点补日志（自下而上插入，避免行号漂移）→ 编译 → 装机（核实）。"""
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
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
if "fun log(msg" not in "".join(L):
    # ① 在 baseUrl 声明之后插 log()
    i = next(k for k, l in enumerate(L) if re.search(r"var baseUrl: String", l))
    eol = "\r\n" if L[i].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[i]).group(1)
    fn = [
        eol,
        ind + "/** 语音链路日志：外部可读文件 + logcat + App 的 LogBus（release 版 adb 可 pull）。 */" + eol,
        ind + "fun log(msg: String) {" + eol,
        ind + "    val line = java.text.SimpleDateFormat(\"MM-dd HH:mm:ss\", java.util.Locale.US)" + eol,
        ind + "        .format(java.util.Date()) + \"  [voice] \" + msg" + eol,
        ind + "    runCatching { android.util.Log.i(\"VoiceClient\", line) }" + eol,
        ind + "    runCatching { com.aipet.murasame.bot.LogBus.log(line) }" + eol,
        ind + "    val c = appCtx ?: return" + eol,
        ind + "    runCatching {" + eol,
        ind + "        java.io.File(c.filesDir, \"voice.log\").appendText(line + \"\\n\")" + eol,
        ind + "        val ext = java.io.File(c.getExternalFilesDir(null) ?: return@runCatching, \"voice.log\")" + eol,
        ind + "        ext.appendText(line + \"\\n\")" + eol,
        ind + "    }" + eol,
        ind + "}" + eol,
    ]
    # appCtx 若不存在则一并声明
    if "var appCtx" not in "".join(L):
        fn = [eol, ind + "@Volatile var appCtx: android.content.Context? = null" + eol] + fn
    L = L[:i + 1] + fn + L[i + 1:]
    s = "".join(L)
    if "appCtx = ctx.applicationContext" not in s:
        s = s.replace("        val v = if (f.isFile) f.readText().trim() else \"\"",
                      "        appCtx = ctx.applicationContext\n"
                      "        val v = if (f.isFile) f.readText().trim() else \"\"", 1)
    io.open(VC, "w", encoding="utf-8", newline="").write(s)
    print("✓ 已加 log() 与 appCtx")

# ② 逐个失败点补日志（自下而上）
L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
targets = []
for k, l in enumerate(L):
    st = l.strip()
    if st == "if (base.isEmpty() || text.isBlank()) return false":
        targets.append((k, 'log("跳过：base=\'" + baseUrl + "\' 文本长=" + text.length)'))
    elif st == "if (!resp.isSuccessful) return false":
        targets.append((k, 'log("HTTP 失败 code=" + resp.code)'))
    elif st.startswith("val bytes = resp.body?.bytes() ?: return false"):
        targets.append((k, 'log("响应体为空")'))
    elif st == "if (bytes.size < 2000) return false          // 太小：多半是 JSON 错误":
        targets.append((k, 'log("响应太小 size=" + bytes.size + " 内容=" + String(bytes).take(120))'))
    elif st == "if (!isRiff) return false":
        targets.append((k, 'log("不是 RIFF size=" + bytes.size + " 头=" + String(bytes).take(16))'))
    elif st == "if (!ok) return false":
        targets.append((k, 'log("合成/落盘失败")'))
for k, msg in sorted(targets, key=lambda x: -x[0]):
    eol = "\r\n" if L[k].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[k]).group(1)
    L[k] = ind + msg + eol + L[k]
print("✓ 已补 %d 处失败日志" % len(targets))
# 成功点
for k, l in enumerate(L):
    if l.strip() == "return true" and "player" not in "".join(L[max(0, k - 6):k]):
        eol = "\r\n" if l.endswith("\r\n") else "\n"
        ind = re.match(r"(\s*)", l).group(1)
        L[k] = ind + 'log("成功播放 " + java.io.File(f.path).length() + " 字节")' + eol + l
        break
io.open(VC, "w", encoding="utf-8", newline="").write("".join(L))
print("✓ 已补成功日志")

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
    print("   第 %d 次安装: %s" % (att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:50]))
    time.sleep(3)
    now = itime()
    print("      lastUpdateTime =", now)
    if now != before and now != "?":
        print("   ✓ 新版已装上")
        break

MSG = """feat(voice): VoiceClient 增加可取证日志（每个失败点都记原因）

用户反馈"朗读还是系统语音"，而电脑端 F5 服务健康（health 0.17s、真合成 6.26s、输出合法 RIFF）。
手机侧此前没有任何语音日志，无法判断 speak() 为什么返回 false。本次补齐：
  - VoiceClient.log()：写外部可读 getExternalFilesDir()/voice.log（adb pull 可取）、
    logcat 标签 VoiceClient、以及 App 的 LogBus；
  - speak() 的每个 return false 之前都记录原因：base 为空、HTTP 状态码、响应体为空、
    响应过小（附带响应片段）、不是 RIFF（附带头部字节）、合成/落盘失败；
  - 成功播放时记录音频字节数。
（同时补 @Volatile appCtx 并在 load() 中赋值，供日志使用。）

验证：编译装机后触发一次朗读，pull voice.log 查看具体失败原因。
"""
msg = os.path.join(MAP, "_msg_voicelog.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
