# -*- coding: utf-8 -*-
"""TTS 接线：① 撤掉 assets/tts（190MB 不进 APK，改 adb push 到外部目录）
   ② 修 VoiceClient.speak 的层级顺序 bug（台词包必须在"有没有电脑地址"之前判）
   ③ 插入离线 TTS 层（Kokoro）④ 编译 + APK 取证 + 写推送脚本"""
import io
import os
import shutil
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
VOICE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


print("=== ① 撤掉 assets/tts（改为 adb push 到 /sdcard/Android/data/<pkg>/files/tts）===")
a = os.path.join(CHAT, "app/src/main/assets/tts")
if os.path.isdir(a):
    tot = sum(os.path.getsize(os.path.join(b, f)) for b, _, fs in os.walk(a) for f in fs)
    shutil.rmtree(a)
    print("   已删 assets/tts（%.1f MB）—— 模型留在电脑缓存 dev/tts_model_cache 供推送" % (tot / 1e6))
else:
    print("   · assets/tts 不存在")

print()
print("=== ②③ 改 VoiceClient.speak ===")
s = io.open(VOICE, encoding="utf-8").read().replace("\r\n", "\n")
old = s[s.find("    /**\n     * 请求电脑 F5-TTS 合成并播放。"):]
if "OfflineTtsEngine" in s:
    print("   · 已接过离线 TTS")
else:
    new_speak = '''    /**
     * 出声（按可靠性分层，逐层降级，**任何一层成功就接手**）：
     *   ① 预生成台词包 assets/voice —— 离线、秒出，**与有没有电脑无关**（此前顺序错了：
     *      早退在 base.isEmpty() 上，导致拔线时连台词包都不用，直接退化成系统 TTS）
     *   ② 联网缓存（电脑合成过的结果）
     *   ③ 电脑 F5-TTS /infer（她真正的音色）
     *   ④ **离线 TTS（本机 Kokoro int8）** —— 不需要电脑、不需要网
     *   ⑤ 返回 false → 调用方回退系统 TTS
     * @return true 表示已接手（调用方不必再回退系统 TTS）；false 表示彻底没辙。
     */
    fun speak(ctx: Context, text: String, refAudio: String? = null, refText: String? = null,
              petId: String? = null): Boolean {
        appCtx = ctx.applicationContext
        if (text.isBlank()) {
            log("文本为空，交回系统 TTS")
            return false
        }
        // ① 台词包：必须最先判（离线可用，不依赖电脑地址）
        if (packed(ctx, text, petId)) return true

        val base = (baseUrl.ifEmpty { load(ctx) }).trim().trimEnd('/')
        val offlineReady = OfflineTtsEngine.isReady(ctx)

        if (base.isNotEmpty()) {
            // ② 缓存
            val f = cacheFile(ctx, text)
            if (f.isFile && f.length() >= 2000) {
                log("命中缓存 " + f.length() + " 字节")
                play(ctx, f)
                return true
            }
            // ③ 电脑合成；失败则落 ④ 离线 TTS
            scope.launch {
                val okSynth = synth(ctx, f, base, text, petId, refAudio, refText)
                if (okSynth) {
                    withContext(Dispatchers.Main) { play(ctx, f) }
                } else if (offlineReady) {
                    log("电脑合成失败 → 改用离线 TTS")
                    withContext(Dispatchers.IO) { speakOffline(ctx, text) }
                } else {
                    log("电脑合成失败且离线 TTS 未就绪：本次不出声")
                }
            }
            return true
        }

        // 没配电脑地址（拔线/热点没开）
        if (offlineReady) {
            log("未配置电脑地址 → 走离线 TTS（不需要电脑）")
            scope.launch { withContext(Dispatchers.IO) { speakOffline(ctx, text) } }
            return true
        }
        log("未配置电脑地址且离线 TTS 未就绪（缺 files/tts/model.int8.onnx）→ 交回系统 TTS")
        return false
    }

    /** 本机离线 TTS（Kokoro int8）。只在 IO 线程调用；内部自己播放。 */
    private fun speakOffline(ctx: Context, text: String): Boolean = runCatching {
        val ms = OfflineTtsEngine.speak(ctx, text, lang = "zh", speakerId = 0)
        log("离线 TTS 返回 " + ms + " ms（" + text.take(12) + "）")
        ms > 0
    }.getOrElse { e ->
        log("离线 TTS 异常：" + e.javaClass.simpleName + " / " + e.message)
        false
    }
}
'''
    s = s[:s.find("    /**\n     * 请求电脑 F5-TTS 合成并播放。")] + new_speak
    if not s.startswith("package com.aipet.murasame.bot.chat"):
        note("文件头被破坏（不回滚，直接报错）", False)
    else:
        # 需要 import OfflineTtsEngine（在 ui 包）
        s = s.replace("import org.json.JSONObject", "import org.json.JSONObject\nimport com.aipet.murasame.ui.OfflineTtsEngine", 1)
        io.open(VOICE, "w", encoding="utf-8", newline="\n").write(s)
        note("已重写 speak（台词包优先 + 离线 TTS 层）", "OfflineTtsEngine.isReady" in s)

if not ok:
    print("✗ 改文件失败，回滚 VoiceClient")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt"], capture_output=True)
    sys.exit(1)

print()
print("=== ④ 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:235])
if r.returncode != 0:
    sys.exit(1)

APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   APK %.1f MB" % (os.path.getsize(APK) / 1e6))
with zipfile.ZipFile(APK) as z:
    names = z.namelist()
    note("APK 里有台词包 voice/index.json", "assets/voice/index.json" in names)
    note("APK 里**没有** 190MB 的 tts 模型（改走外部目录推送）",
         not any(n.startswith("assets/tts/") for n in names))

# 推送脚本
ps = os.path.join(MAIN, "dev", "scripts", "push_tts_model.py")
io.open(ps, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""把离线 TTS 模型推到手机外部目录（Android/data/<pkg>/files/tts）。
   模型 190MB 不进 APK：OfflineTtsEngine.modelDir() 查的就是这个外部目录。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\\Android\\SDK\\platform-tools\\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
SRC = r"E:\\university\\order\\python\\pet\\AIpet-Murasame-main\\dev\\tts_model_cache\\extracted\\kokoro-int8-multi-lang-v1_0"
DST = "/sdcard/Android/data/%s/files/tts" % PKG

print("可用设备:")
print(subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout)
if DEV not in subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout:
    print("✗ 手机不在线，先插线或开热点")
    sys.exit(1)
subprocess.run([ADB, "-s", DEV, "shell", "mkdir", "-p", DST], capture_output=True)
print("推送 %s → %s（约 190MB，慢的话等一会儿）" % (os.path.basename(SRC), DST))
r = subprocess.run([ADB, "-s", DEV, "push", SRC + "/.", DST], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=3600)
print((r.stdout or r.stderr or "").strip()[-300:])
print("校验:")
print(subprocess.run([ADB, "-s", DEV, "shell", "ls", "-l", DST + "/model.int8.onnx",
                      DST + "/voices.bin", DST + "/tokens.txt"], capture_output=True, text=True).stdout)
print(subprocess.run([ADB, "-s", DEV, "shell", "ls", DST + "/espeak-ng-data | wc -l"],
                     capture_output=True, text=True).stdout.strip(), "个 espeak 文件")
''')
print("✓ 已写 dev/scripts/push_tts_model.py（手机上线后一键推送 190MB 模型）")
