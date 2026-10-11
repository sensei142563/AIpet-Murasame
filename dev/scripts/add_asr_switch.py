# -*- coding: utf-8 -*-
"""设置页加「离线识别（实验）」开关 + 自检行显示当前状态；编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
old = '''    // [voice-test] 一键试听：直接调 VoiceClient（不经过聊天流程），便于验证语音链路
    Row2("识别自检", "离线识别内置样例，结果写入日志（验收用）",
Icons.Default.Mic, text, sub) {
runCatching { com.aipet.murasame.ui.OnlineAsr.selfTest(vctx) }
}'''
new = '''    // [asr-switch] 离线识别总开关（可见化）
    // 默认停用：真机实测该原生库一初始化就让 App 直接退出（Java 侧、crash buffer、dropbox 全无痕迹）。
    // 做成开关，既能一眼看出当前状态，也方便你自己试验/恢复，不用去手写文件。
    var offlineAsr by remember {
        mutableStateOf(com.aipet.murasame.ui.OnlineAsr.offlineEnabled(vctx))
    }
    Row2(
        "离线识别（实验）",
        if (offlineAsr) "已开启 —— 本机实测会在初始化时让 App 直接退出，谨慎使用"
        else "已停用（推荐）—— 语音输入改走系统识别",
        Icons.Default.Mic, text, sub
    ) {
        val f = java.io.File(vctx.getExternalFilesDir(null) ?: vctx.filesDir,
            "asr_offline_enabled.txt")
        runCatching {
            if (offlineAsr) f.delete() else { f.parentFile?.mkdirs(); f.writeText("1") }
        }
        offlineAsr = !offlineAsr
    }
    // [voice-test] 一键试听：直接调 VoiceClient（不经过聊天流程），便于验证语音链路
    Row2("识别自检",
        if (offlineAsr) "离线识别内置样例，结果写入日志（验收用）"
        else "离线识别已停用，自检不会执行（先打开上面的开关）",
        Icons.Default.Mic, text, sub) {
        runCatching { com.aipet.murasame.ui.OnlineAsr.selfTest(vctx) }
    }'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(SP, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 设置页已加「离线识别（实验）」开关 + 自检行状态提示")
else:
    print("✗ 锚点未命中")

print()
print("=== 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")
