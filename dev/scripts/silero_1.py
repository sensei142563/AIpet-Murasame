# -*- coding: utf-8 -*-
"""Silero VAD 包装（sherpa-onnx，无需新依赖）+ 接进 OnlineAsr（Silero 优先、能量法兜底）+ 编译提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

io.open(os.path.join(UI, "SileroVad.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.ui

import android.content.Context
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.Vad
import com.k2fsa.sherpa.onnx.VadModelConfig
import java.io.File

/**
 * Silero VAD（真模型，替代能量法）。
 *
 * 为什么需要：能量法分不出"很大的纯音"和"说话" —— 一个响亮的正弦音也会过闸门，
 * 然后被识别模型瞎猜（实测 whisper 把一段嗡嗡声识别成 "Teksting av Nicolai Winther"）。
 * Silero 是真正的语音/非语音判别模型，0.64MB，sherpa-onnx（**项目已有依赖**）自带支持。
 *
 * API 全部来自 AAR 的 javap 实测（不是猜的）：
 *   Vad(AssetManager, VadModelConfig)
 *   SileroVadModelConfig(model: String, threshold: Float, minSilenceDuration: Float,
 *                        minSpeechDuration: Float, windowSize: Int, maxSpeechDuration: Float)
 *   VadModelConfig(sileroVadModelConfig, tenVadModelConfig, sampleRate: Int,
 *                  numThreads: Int, provider: String, debug: Boolean)
 *   vad.acceptWaveform(FloatArray) / isSpeechDetected(): Boolean
 *   vad.flush() / front(): SpeechSegment(start: Int, samples: FloatArray) / pop() / empty()
 *
 * 模型文件：assets/vad/silero_vad.onnx（0.64MB，sha256 前缀 9e2449e1087496d8）。
 * 注意：**真机未验证** —— 手机不在手边；API 名与模型文件都已核对，但运行时行为需上机确认。
 */
object SileroVad {

    private const val ASSET = "vad/silero_vad.onnx"
    private const val WINDOW = 512          // silero v5 常用 512 采样/窗口（16kHz）

    @Volatile private var vad: Vad? = null
    @Volatile private var failed = false

    private fun log(ctx: Context, msg: String) = runCatching {
        File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "vad.log")
            .appendText(java.text.SimpleDateFormat("MM-dd HH:mm:ss", java.util.Locale.US)
                .format(java.util.Date()) + "  " + msg + "\\n")
    }.let { }

    /** 把模型从 assets 复制到私有目录（Vad 用绝对路径最稳，和 TTS 那边一致的做法）。 */
    private fun modelFile(ctx: Context): File? = runCatching {
        val f = File(ctx.filesDir, "vad/silero_vad.onnx")
        if (f.isFile && f.length() > 100000) return f
        f.parentFile?.mkdirs()
        ctx.assets.open(ASSET).use { ins -> f.outputStream().use { ins.copyTo(it) } }
        if (f.length() > 100000) f else null
    }.getOrNull()

    fun isAvailable(ctx: Context): Boolean = runCatching {
        ctx.assets.open(ASSET).close(); true
    }.getOrDefault(false)

    fun init(ctx: Context): Boolean {
        vad?.let { return true }
        if (failed) return false
        val mf = modelFile(ctx) ?: run { log(ctx, "模型复制失败"); failed = true; return false }
        return runCatching {
            val silero = SileroVadModelConfig(
                model = mf.absolutePath,
                threshold = 0.5f,
                minSilenceDuration = 0.25f,
                minSpeechDuration = 0.20f,
                windowSize = WINDOW,
                maxSpeechDuration = 20.0f,
            )
            val cfg = VadModelConfig(
                sileroVadModelConfig = silero,
                sampleRate = 16000,
                numThreads = 1,
                provider = "cpu",
                debug = false,
            )
            vad = Vad(assetManager = ctx.assets, config = cfg)
            log(ctx, "Silero VAD ready (model=%d 字节)".format(mf.length()))
            true
        }.getOrElse { e ->
            log(ctx, "init 失败：%s: %s".format(e.javaClass.simpleName, e.message))
            failed = true
            false
        }
    }

    data class Result(val isSpeech: Boolean, val startSample: Int, val endSample: Int, val detail: String)

    /**
     * 判断这段音频里有没有人说话，并给出第一段语音的区间。
     * 失败/未就绪时返回 null，调用方应回退到能量法 VadGate。
     */
    fun analyze(ctx: Context, samples: FloatArray, sampleRate: Int = 16000): Result? {
        if (!init(ctx)) return null
        val v = vad ?: return null
        return runCatching {
            v.reset()
            var i = 0
            while (i < samples.size) {
                val n = minOf(WINDOW, samples.size - i)
                val chunk = if (n == WINDOW) samples.copyOfRange(i, i + n)
                else FloatArray(WINDOW).also { samples.copyOfRange(i, i + n).copyInto(it) }
                v.acceptWaveform(chunk)
                i += n
            }
            v.flush()
            val segs = mutableListOf<Pair<Int, Int>>()
            while (!v.empty()) {
                val seg = v.front()
                if (seg != null) {
                    val start = seg.start
                    val len = seg.samples?.size ?: 0
                    if (len > 0) segs.add(start to (start + len))
                }
                v.pop()
            }
            val total = segs.sumOf { it.second - it.first }
            val isSpeech = v.isSpeechDetected() || total > sampleRate / 5
            val first = segs.firstOrNull()
            Result(isSpeech,
                first?.first ?: 0,
                first?.second ?: 0,
                "Silero%s segs=%d samples=%d".format(if (isSpeech) "命中" else "未命中", segs.size, total))
        }.getOrElse { e ->
            log(ctx, "analyze 失败：%s: %s".format(e.javaClass.simpleName, e.message))
            null
        }
    }
}
''')
print("✓ 新增 ui/SileroVad.kt")

# 接进 OnlineAsr：Silero 优先，能量法兜底
OA = os.path.join(UI, "OnlineAsr.kt")
t = io.open(OA, encoding="utf-8").read().replace("\r\n", "\n")
old = """        val vad = VadGate.analyze(raw, 16000)
        log(ctx, "录音 %d 样本 → %s".format(raw.size, VadGate.describe(vad)))
        if (!vad.isSpeech) {
            log(ctx, "没检测到人声，跳过识别（避免噪声幻觉）")
            return ""
        }
        val s = VadGate.trim(raw, vad)"""
new = """        // 先过 VAD：真模型 Silero 优先（能区分"大纯音"与"说话"），能量法兜底
        val sil = SileroVad.analyze(ctx, raw, 16000)
        val isSpeech: Boolean
        val s: FloatArray
        if (sil != null) {
            isSpeech = sil.isSpeech
            s = if (sil.endSample > sil.startSample) raw.copyOfRange(sil.startSample, sil.endSample) else raw
            log(ctx, "录音 %d 样本 → %s".format(raw.size, sil.detail))
        } else {
            val e = VadGate.analyze(raw, 16000)
            isSpeech = e.isSpeech
            s = VadGate.trim(raw, e)
            log(ctx, "录音 %d 样本 → %s（Silero 不可用，用能量法）".format(raw.size, VadGate.describe(e)))
        }
        if (!isSpeech) {
            log(ctx, "没检测到人声，跳过识别（避免噪声幻觉）")
            return ""
        }"""
if old in t:
    t = t.replace(old, new, 1)
    io.open(OA, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ OnlineAsr 已改为 Silero 优先、能量法兜底")
else:
    print("✗ 未命中 OnlineAsr 锚点")
    sys.exit(1)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:12]:
    print("   " + y[:230])
if r.returncode != 0:
    print("✗ 编译失败（未提交）")
    sys.exit(1)

print()
print("=== APK 取证：模型是否打进去 ===")
import zipfile
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
with zipfile.ZipFile(APK) as z:
    names = z.namelist()
    hit = [n for n in names if "silero" in n.lower()]
    print("   APK %.1f MB" % (os.path.getsize(APK) / 1e6))
    print("   含 silero 模型: %s" % (hit or "✗"))

MSG = """feat(stt): 接入 Silero VAD 真模型（0.64MB，sherpa-onnx 自带，无新依赖）—— 补掉能量法的边界

上一轮如实标注了能量法 VAD 的边界：分不出"很大的纯音"和"说话"。本轮上真模型。

取证过程（不猜 API）：
  · 从 AAR 里解出 classes.jar，用 javap **实测**签名：
      Vad(AssetManager, VadModelConfig) / acceptWaveform(FloatArray) /
      isSpeechDetected(): Boolean / flush() / front(): SpeechSegment(start, samples) / pop()
      SileroVadModelConfig(model, threshold, minSilenceDuration, minSpeechDuration,
                           windowSize, maxSpeechDuration)
      VadModelConfig(sileroVadModelConfig, tenVadModelConfig, sampleRate, numThreads, provider, debug)
  · 模型：官方 release 的 silero_vad.onnx，**0.64MB**，sha256 前缀 9e2449e1087496d8，
    已放入 app/src/main/assets/vad/silero_vad.onnx（小，直接进 APK）。

新增 ui/SileroVad.kt：
  · init()：把 assets 里的模型复制到私有目录（绝对路径最稳，与 TTS 那边一致），
    用 SileroVadModelConfig(threshold=0.5, minSilence=0.25s, minSpeech=0.20s, window=512) 建 Vad；
  · analyze()：按 512 采样窗口喂完整段音频 → flush() → 取 front()/pop() 得到的语音段，
    返回是否有人声 + 第一段区间 + 一行摘要；任何异常返回 null。
OnlineAsr.recognizeWav：**Silero 优先，不可用时回退能量法 VadGate**（保留上一轮已验证的兜底），
判定无人声仍直接返回空、不把噪声送进识别器。

诚实标注：**真机未验证** —— API 名与模型文件都已核对，但运行时行为（阈值是否合适、
window 是否需按模型版本调整）要等手机上机确认。能量法的 7 个单测仍然有效（兜底路径）。
"""
p = os.path.join(MAP, "_msg_silero1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
