# -*- coding: utf-8 -*-
"""① ASR 自测：加前后日志 + 每进程只跑一次（避免重复/并发的原生模型初始化）
   ② TTS 引擎创建/销毁加日志
   ③ 聊天页组合埋点加上"关键状态"，避免只看到重复的同一行
编译装机后自测。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")

# ---------- ① ASR 自测：加日志 + 每进程一次 ----------
old = '''    LaunchedEffect(petId) {

        // [asr] 离线识别自测（用模型包自带的中文音频；结果写 live2d.log）
        kotlinx.coroutines.withContext(Dispatchers.IO) { runCatching { OnlineAsr.selfTest(ctx) } }'''
new = '''    LaunchedEffect(petId) {

        // [asr] 离线识别自测（用模型包自带的中文音频；结果写 live2d.log）
        // 真机实测：进入聊天页时进程会被内核收走（appDiedLocked fromBinderDied=true、
        // 无 Java 异常、无 Fatal signal、onDestroy 都没执行 ⇒ 原生层直接崩）。
        // 这里唯一的重活就是这个原生模型自测，而聊天页可能被重复组合/重建 ⇒ 每进程只跑一次，
        // 并前后打点：万一还是崩，日志里最后一条就能指出是不是它。
        if (!asrSelfTestDone) {
            asrSelfTestDone = true
            com.aipet.murasame.Diag.log("Chat", "ASR 自测 开始（原生模型初始化）")
            kotlinx.coroutines.withContext(Dispatchers.IO) { runCatching { OnlineAsr.selfTest(ctx) } }
            com.aipet.murasame.Diag.log("Chat", "ASR 自测 返回（没崩）")
        } else {
            com.aipet.murasame.Diag.log("Chat", "ASR 自测 跳过（本进程已跑过）")
        }'''
if old in t:
    t = t.replace(old, new, 1)
    print("✓ ① ASR 自测已加日志 + 每进程一次")
else:
    print("✗ ASR 自测锚点未命中")

# 全局标志（放在 ChatScreen 函数外，文件末尾）
if "asrSelfTestDone" in t and "private var asrSelfTestDone" not in t:
    t = t.rstrip() + '''

/** 进程级标志：原生模型自测每进程只跑一次（重复初始化会导致原生崩溃）。 */
@Volatile
private var asrSelfTestDone = false
'''
    print("✓ 已加 asrSelfTestDone 标志")

# ---------- ② TTS 引擎日志 ----------
t = t.replace("        tts = engine\n        onDispose { runCatching { engine.stop(); engine.shutdown() } }",
              '''        tts = engine
        com.aipet.murasame.Diag.log("Chat", "系统 TTS 引擎已创建")
        onDispose {
            com.aipet.murasame.Diag.log("Chat", "系统 TTS 引擎 onDispose")
            runCatching { engine.stop(); engine.shutdown() }
        }''', 1)

# ---------- ③ 组合埋点加更多上下文（只打关键几次）----------
io.open(CS, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装机：" + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无)"])[-1][:120])


def adb(*a, timeout=180):
    rr = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=timeout)
    return (rr.stdout or "") + (rr.stderr or "")


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:88]
    return "(未知)"


print("\n=== 关市场弹窗 ===")
adb("shell", "uiautomator", "dump", "/sdcard/mk4.xml")
adb("pull", "/sdcard/mk4.xml", os.path.join(SD, "mk4.xml"))
xm = io.open(os.path.join(SD, "mk4.xml"), encoding="utf-8", errors="replace").read() if os.path.isfile(os.path.join(SD, "mk4.xml")) else ""
for lb in ("完成", "开启"):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % lb, xm) or \
        re.search(r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="%s"' % lb, xm)
    if m:
        adb("shell", "input", "tap", str((int(m.group(1)) + int(m.group(3))) // 2),
            str((int(m.group(2)) + int(m.group(4))) // 2))
        print("   点了「%s」" % lb)
        time.sleep(3)
        break
else:
    adb("shell", "am", "force-stop", "com.huawei.appmarket")
    time.sleep(2)

print("\n=== 清日志 → 启动 → 点「聊天」 ===")
adb("shell", "rm", "-f", EXT + "/diag.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
adb("shell", "input", "tap", "1112", "2695")
time.sleep(10)
print("   点击后前台:", fg())

print("\n=== diag.log ===")
log = adb("shell", "cat", EXT + "/diag.log")
print("\n".join("   " + l for l in (log or "(空)").splitlines()[-45:]))
