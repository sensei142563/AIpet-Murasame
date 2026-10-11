# -*- coding: utf-8 -*-
"""① OfflineTtsEngine 加总开关（默认关：本机实测原生构造函数会无限卡住）
   ② 删掉遗留诊断函数 diagEmptyConfigOnMain（避免以后再被调）
   ③ 设置页加「离线音色（实验）」开关行 + 说明
   ④ 编译装机 + 复验"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ENG = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/OfflineTtsEngine.kt")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 引擎总开关 ----------
t = io.open(ENG, encoding="utf-8").read().replace("\r\n", "\n")
if "offlineTtsEnabled" not in t:
    helper = '''
    /**
     * 离线合成总开关：**默认停用**。
     *
     * 真机实测（MIS-AL00 / Android 12）：sherpa-onnx 的 Kokoro 原生构造函数
     * **无限卡住** —— 触发后等到 90 秒仍无 "ready" 也无异常（连 init failed 都没有），
     * 而界面还响应正常，说明是原生层死等，runCatching 兜不住。
     * 同机的 SenseVoice（离线识别）则是初始化解崩掉进程，两个原生组件在本机都不能用。
     * 需要试验时在设备上创建：files/tts_offline_enabled.txt 内容写 1。
     */
    fun offlineEnabled(ctx: Context): Boolean = runCatching {
        val f = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "tts_offline_enabled.txt")
        f.isFile && f.readText().trim() == "1"
    }.getOrDefault(false)
'''
    t = t.replace("    private fun log(ctx: Context, msg: String)",
                  helper + "\n    private fun log(ctx: Context, msg: String)", 1)
    t = t.replace('''    fun init(ctx: Context, lang: String = "ja"): Boolean {
        log(ctx, "init() 进入 lang=" + lang + " modelDir=" + (modelDir(ctx)?.absolutePath ?: "无"))''',
                  '''    fun init(ctx: Context, lang: String = "ja"): Boolean {
        log(ctx, "init() 进入 lang=" + lang + " modelDir=" + (modelDir(ctx)?.absolutePath ?: "无"))
        // 停用时**根本不构造原生对象**（构造即卡死，见 offlineEnabled 说明）
        if (!offlineEnabled(ctx)) {
            log(ctx, "离线合成已停用（本机原生库会卡死）⇒ 本次不合成，改用系统语音/电脑 F5")
            return false
        }''', 1)
    # 删除遗留诊断函数
    t = re.sub(r"\n    /\*\* 主线程版本：不切换线程直接构造[\s\S]*?\n    \}\n", "\n", t)
    io.open(ENG, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ① OfflineTtsEngine 已加总开关 + ② 遗留诊断函数已删除")
else:
    print("· 引擎已有开关")

# ---------- ③ 设置页开关行 ----------
s = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
if "tts_offline_enabled" not in s:
    anchor = '''    Row2("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）",'''
    add = '''    // [tts-switch] 离线合成总开关（可见化）
    // 默认停用：真机实测 Kokoro 原生构造函数会无限卡住（90 秒无结果也无异常，runCatching 兜不住）。
    var offlineTts by remember {
        mutableStateOf(com.aipet.murasame.ui.OfflineTtsEngine.offlineEnabled(vctx))
    }
    Row2(
        "离线音色（实验）",
        if (offlineTts) "已开启 —— 本机实测会卡在模型加载上，建议改回系统语音或电脑 F5"
        else "已停用（推荐）—— 本机原生库会卡死；用系统语音或电脑 F5",
        Icons.Default.VolumeUp, text, sub
    ) {
        val f = java.io.File(vctx.getExternalFilesDir(null) ?: vctx.filesDir,
            "tts_offline_enabled.txt")
        runCatching {
            if (offlineTts) f.delete() else { f.parentFile?.mkdirs(); f.writeText("1") }
        }
        offlineTts = !offlineTts
    }
    Row2("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）",'''
    if anchor in s:
        s = s.replace(anchor, add, 1)
        io.open(SP, "w", encoding="utf-8", newline="\n").write(s)
        print("✓ ③ 设置页已加「离线音色（实验）」开关行")
    else:
        print("✗ ③ 设置页锚点未命中")
else:
    print("· 设置页已有开关")

print()
print("=== ④ 编译 + 装机 ===")
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
