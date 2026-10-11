# -*- coding: utf-8 -*-
"""把 ASR 自测从聊天页组合里彻底移除（它只是诊断用，却在你手机上原生崩溃）。
保留：真实识别路径不动；自检改为**只在设置页手动点**时运行（由设置页的按钮触发）。
编译装机后自测聊天页能否正常打开并停留。"""
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
old = '''        if (!asrSelfTestDone) {
            asrSelfTestDone = true
            com.aipet.murasame.Diag.log("Chat", "ASR 自测 开始（原生模型初始化）")
            kotlinx.coroutines.withContext(Dispatchers.IO) { runCatching { OnlineAsr.selfTest(ctx) } }
            com.aipet.murasame.Diag.log("Chat", "ASR 自测 返回（没崩）")
        } else {
            com.aipet.murasame.Diag.log("Chat", "ASR 自测 跳过（本进程已跑过）")
        }'''
new = '''        // 【已移除】原来这里会跑 OnlineAsr.selfTest(ctx)（加载 SenseVoice 原生模型做识别自检）。
        // 真机实测（MIS-AL00 / Android 12）：它一执行就让**原生层崩溃**、进程被内核收走，
        // 表现就是"一切到聊天页就闪退"（Java 异常处理器、crash buffer、dropbox 里全都查不到，
        // 因为根本没走到 Java 层）。它本来只是验证用的诊断代码，不该在进入页面时跑，故移除。
        // 需要自检时请在设置页手动点「识别自检」。'''
if old in t:
    t = t.replace(old, new, 1)
    print("✓ 已移除聊天页里的 ASR 自测调用")
else:
    print("✗ 锚点未命中（打印现状）")
    i = t.find("ASR 自测")
    print(t[max(0, i - 400):i + 400])

# 清掉不再使用的进程级标志
t = re.sub(r"\n/\*\* 进程级标志：原生模型自测每进程只跑一次（重复初始化会导致原生崩溃）。 \*/\n@Volatile\nprivate var asrSelfTestDone = false\n", "\n", t)
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
adb("shell", "uiautomator", "dump", "/sdcard/mk5.xml")
adb("pull", "/sdcard/mk5.xml", os.path.join(SD, "mk5.xml"))
xm = io.open(os.path.join(SD, "mk5.xml"), encoding="utf-8", errors="replace").read() if os.path.isfile(os.path.join(SD, "mk5.xml")) else ""
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

print("\n=== 清日志 → 启动 → 点「聊天」→ 等 15 秒看是否还活着 ===")
adb("shell", "rm", "-f", EXT + "/diag.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(9)
adb("shell", "input", "tap", "1112", "2695")
for w in (5, 10, 15):
    time.sleep(5)
    p = (adb("shell", "pidof", PKG) or "").strip()
    print("   [%2ds] pid=%s 前台=%s" % (w, p or "(空=进程没了)", fg()))

print("\n=== diag.log 尾部 ===")
log = adb("shell", "cat", EXT + "/diag.log")
print("\n".join("   " + l for l in (log or "(空)").splitlines()[-30:]))
