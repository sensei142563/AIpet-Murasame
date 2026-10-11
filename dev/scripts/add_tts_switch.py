# -*- coding: utf-8 -*-
"""用精确锚点插入「离线音色（实验）」开关行 → 编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

s = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
anchor = 'Row2("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）",'
add = '''// [tts-switch] 离线合成总开关（可见化，默认停用）
// 真机实测：Kokoro 原生构造函数**无限卡住**（90 秒无结果也无异常，runCatching 兜不住），
// 与离线识别的原生化崩同属"本机原生库不可用"。做成开关一眼可见、也可自己试验/恢复。
var offlineTts by remember {
    mutableStateOf(com.aipet.murasame.ui.OfflineTtsEngine.offlineEnabled(vctx))
}
Row2(
    "离线音色（实验）",
    if (offlineTts) "已开启 —— 本机实测会卡在模型加载上；建议改回系统语音或电脑 F5"
    else "已停用（推荐）—— 本机原生库会卡死；请用系统语音或电脑 F5",
    Icons.Default.VolumeUp, text, sub
) {
    val f = java.io.File(vctx.getExternalFilesDir(null) ?: vctx.filesDir,
        "tts_offline_enabled.txt")
    runCatching {
        if (offlineTts) f.delete() else { f.parentFile?.mkdirs(); f.writeText("1") }
    }
    offlineTts = !offlineTts
}
'''
if "tts_offline_enabled" in s:
    print("· 已有开关行")
elif anchor in s:
    s = s.replace(anchor, add + anchor, 1)
    io.open(SP, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已插入「离线音色（实验）」开关行")
else:
    print("✗ 精确锚点仍未命中")

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
