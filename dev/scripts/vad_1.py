# -*- coding: utf-8 -*-
"""VAD/静音剔除：ui/VadGate.kt（纯计算 + 单测）+ 接进 OnlineAsr.recognizeWav。"""
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

io.open(os.path.join(UI, "VadGate.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.ui

import kotlin.math.sqrt

/**
 * 语音活动检测（VAD）/ 静音剔除（**纯计算，可 JVM 单测**）。
 *
 * 为什么需要它：实测发现 whisper 对**噪声**会"编内容" —— 我一段合成的嗡嗡声探针被识别成
 * "Teksting av Nicolai Winther"。SenseVoice 这类模型同样存在低信噪比下的乱猜。
 * 所以送进识别器之前必须先判断"这段里到底有没有人说话"，并把前后静音裁掉。
 *
 * 算法（刻意保持简单、可解释、可单测）：
 *   1) 按 20ms 分帧算 RMS；
 *   2) 噪声底 = 各帧 RMS 的 **20 百分位**（比取最小值稳健：不会被某一帧的纯零拉偏）；
 *   3) 某帧算"有声"当且仅当 rms > max(absFloor, noiseFloor × relThreshold)；
 *   4) 取"有声帧"的首尾区间，累计时长 ≥ minSpeechMs 才算真的说了话；
 *   5) 返回裁剪区间，供调用方只把这段送去识别（顺带省流量、减少边缘幻觉）。
 *
 * 边界：这是能量法，不认识音素；强烈推荐在低信噪比环境配合更专业的 VAD。
 */
object VadGate {

    data class Result(
        val isSpeech: Boolean,
        val startSample: Int,
        val endSample: Int,
        val speechMs: Int,
        val noiseRms: Float,
        val peakRms: Float,
        val frames: Int,
    )

    /** 逐帧 RMS。 */
    fun frameRms(samples: FloatArray, frameLen: Int): FloatArray {
        if (frameLen <= 0 || samples.isEmpty()) return FloatArray(0)
        val n = samples.size / frameLen
        val out = FloatArray(n)
        for (i in 0 until n) {
            var acc = 0.0
            val from = i * frameLen
            for (j in from until from + frameLen) {
                val v = samples[j].toDouble()
                acc += v * v
            }
            out[i] = sqrt(acc / frameLen).toFloat()
        }
        return out
    }

    /** 百分位（p 取 0..1）。 */
    fun percentile(values: FloatArray, p: Float): Float {
        if (values.isEmpty()) return 0f
        val sorted = values.clone()
        sorted.sort()
        val idx = ((sorted.size - 1) * p).toInt().coerceIn(0, sorted.size - 1)
        return sorted[idx]
    }

    fun analyze(samples: FloatArray, sampleRate: Int = 16000, frameMs: Int = 20,
                minSpeechMs: Int = 200, relThreshold: Float = 3.0f,
                absFloor: Float = 0.006f, padMs: Int = 150): Result {
        val frameLen = (sampleRate * frameMs / 1000).coerceAtLeast(1)
        val rms = frameRms(samples, frameLen)
        if (rms.isEmpty()) return Result(false, 0, 0, 0, 0f, 0f, 0)
        val noise = percentile(rms, 0.20f)
        val gate = maxOf(absFloor, noise * relThreshold)
        var first = -1
        var last = -1
        var peak = 0f
        for (i in rms.indices) {
            if (rms[i] > peak) peak = rms[i]
            if (rms[i] > gate) {
                if (first < 0) first = i
                last = i
            }
        }
        if (first < 0) return Result(false, 0, 0, 0, noise, peak, rms.size)
        val speechFrames = last - first + 1
        val speechMs = speechFrames * frameMs
        if (speechMs < minSpeechMs) return Result(false, 0, 0, speechMs, noise, peak, rms.size)
        val padLen = (sampleRate * padMs / 1000)
        val s = (first * frameLen - padLen).coerceAtLeast(0)
        val e = ((last + 1) * frameLen + padLen).coerceAtMost(samples.size)
        return Result(true, s, e, speechMs, noise, peak, rms.size)
    }

    /** 只要"有人说话"的那一段（没有则返回空数组）。 */
    fun trim(samples: FloatArray, r: Result): FloatArray =
        if (!r.isSpeech || r.endSample <= r.startSample) FloatArray(0)
        else samples.copyOfRange(r.startSample, r.endSample)

    /** 一行摘要（写日志用）。 */
    fun describe(r: Result): String =
        "VAD%s speechMs=%d noise=%.4f peak=%.4f frames=%d".format(
            if (r.isSpeech) "命中" else "未命中", r.speechMs, r.noiseRms, r.peakRms, r.frames)
}
''')
print("✓ 新增 ui/VadGate.kt")

# 接线：OnlineAsr.recognizeWav 里先过 VAD
OA = os.path.join(UI, "OnlineAsr.kt")
t = io.open(OA, encoding="utf-8").read().replace("\r\n", "\n")
if "VadGate" in t:
    print("· OnlineAsr 已接 VAD")
else:
    old = """        val s = readWav(path)"""
    new = """        val raw = readWav(path)
        // 先过 VAD：没说话就直接返回，别把噪声送进识别器（噪声会被"编"出内容，
        // 实测 whisper 把一段嗡嗡声识别成 "Teksting av Nicolai Winther"）。
        val vad = VadGate.analyze(raw, 16000)
        log(ctx, "录音 %d 样本 → %s".format(raw.size, VadGate.describe(vad)))
        if (!vad.isSpeech) {
            log(ctx, "没检测到人声，跳过识别（避免噪声幻觉）")
            return ""
        }
        val s = VadGate.trim(raw, vad)"""
    if old in t:
        t = t.replace(old, new, 1)
        io.open(OA, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ OnlineAsr.recognizeWav 已接 VAD（无语音直接返回空）")
    else:
        print("⚠ 未命中 readWav 锚点")

io.open(os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/VadGateTest.kt"),
        "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import com.aipet.murasame.ui.VadGate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI
import kotlin.math.sin

/** VAD 的纯计算单测：静音 / 突发 / 短促咔哒 / 噪声底自适应 / 裁剪边界。 */
class VadGateTest {

    private val sr = 16000

    private fun silence(ms: Int, amp: Float = 0.0005f): FloatArray =
        FloatArray(sr * ms / 1000) { amp * (if (it % 2 == 0) 1f else -1f) }

    private fun tone(ms: Int, amp: Float, freq: Double = 440.0): FloatArray =
        FloatArray(sr * ms / 1000) { (amp * sin(2 * PI * freq * it / sr)).toFloat() }

    private fun concat(vararg parts: FloatArray): FloatArray {
        val out = FloatArray(parts.sumOf { it.size })
        var o = 0
        for (p in parts) { p.copyInto(out, o); o += p.size }
        return out
    }

    @Test
    fun pure_silence_is_not_speech() {
        val r = VadGate.analyze(silence(1000), sr)
        assertFalse("静音不应判为说话", r.isSpeech)
        assertEquals(0, VadGate.trim(silence(1000), r).size)
    }

    @Test
    fun burst_in_silence_is_speech_and_trimmed() {
        val sig = concat(silence(400), tone(600, 0.25f), silence(400))
        val r = VadGate.analyze(sig, sr)
        assertTrue("中间有 600ms 语音应命中", r.isSpeech)
        assertTrue("语音时长接近 600ms（含帧量化）：${r.speechMs}", r.speechMs in 560..700)
        val cut = VadGate.trim(sig, r)
        assertTrue("裁剪后应明显短于原信号", cut.size < sig.size)
        assertTrue("裁剪后应长于语音本身（含 pad）", cut.size > sr * 600 / 1000)
    }

    @Test
    fun short_click_is_rejected() {
        // 60ms 的咔哒：小于 minSpeechMs=200 ⇒ 不算说话（避免误触发）
        val sig = concat(silence(300), tone(60, 0.4f), silence(300))
        val r = VadGate.analyze(sig, sr)
        assertFalse("短促咔哒不应算说话（speechMs=${r.speechMs}）", r.isSpeech)
        assertEquals(60, r.speechMs)
    }

    @Test
    fun loud_steady_noise_is_not_speech() {
        // 持续大声噪声：噪声底会被抬高，于是不该判成说话（这正是"自适应"的意义）
        val sig = tone(1500, 0.2f, 300.0)
        val r = VadGate.analyze(sig, sr)
        assertFalse("持续噪声不应判为说话（noise=${r.noiseRms}, peak=${r.peakRms}）", r.isSpeech)
    }

    @Test
    fun speech_over_noise_is_detected() {
        // 底噪 0.01 + 语音 0.2 ⇒ 阈值 = max(0.006, 0.01*3=0.03) = 0.03，语音远超
        val sig = concat(tone(500, 0.01f, 220.0), tone(500, 0.2f, 440.0), tone(500, 0.01f, 220.0))
        val r = VadGate.analyze(sig, sr)
        assertTrue("噪声之上的语音应被检出", r.isSpeech)
        assertTrue("应主要覆盖中间那段：speechMs=${r.speechMs}", r.speechMs in 450..600)
    }

    @Test
    fun percentile_is_robust() {
        val v = floatArrayOf(0.01f, 0.02f, 0.03f, 0.5f, 0.9f)
        assertEquals(0.02f, VadGate.percentile(v, 0.20f), 0.005f)
        assertEquals(0.9f, VadGate.percentile(v, 1.0f), 0.0001f)
    }

    @Test
    fun empty_input_is_safe() {
        val r = VadGate.analyze(FloatArray(0), sr)
        assertFalse(r.isSpeech)
        assertEquals(0, VadGate.trim(FloatArray(0), r).size)
    }
}
''')
print("✓ 新增 test/.../VadGateTest.kt")

print()
print("=== 跑单测 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.VadGateTest"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
for l in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: |AssertionError", l):
        print("   " + l.strip()[:175])
p2 = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest/TEST-com.aipet.murasame.VadGateTest.xml")
if os.path.isfile(p2):
    x = io.open(p2, encoding="utf-8", errors="replace").read()
    m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
    print("   VadGateTest: tests=%s failures=%s errors=%s" % (m.group(1), m.group(2), m.group(3)))
    if m.group(2) != "0" or m.group(3) != "0":
        for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<failure[^>]*>([^<]{0,220})', x):
            print("      失败 %s → %s" % (mm.group(1), mm.group(2).replace("\n", " ")[:190]))
        sys.exit(1)
