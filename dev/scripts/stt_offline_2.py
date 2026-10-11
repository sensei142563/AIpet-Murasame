# -*- coding: utf-8 -*-
"""STT 升级②：换成非流式 SenseVoice（OfflineRecognizer），对外 API 保持不变；
   并用 torchaudio 正确重采样出 16kHz 验收样例 → 编译装机。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
ONLINE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/OnlineAsr.kt")
ASSETS = os.path.join(CHAT, "app/src/main/assets")
NEWDIR = "asr-sensevoice"
REPO = "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
FILES = ["model.int8.onnx", "tokens.txt"]
UA = {"User-Agent": "Mozilla/5.0 (aipet-stt)"}
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 下载 ----------
d = os.path.join(ASSETS, NEWDIR)
os.makedirs(d, exist_ok=True)
print("=== ① 下载 SenseVoice ===")
for n in FILES:
    fp = os.path.join(d, n)
    if os.path.isfile(fp) and os.path.getsize(fp) > 10000:
        print("   · 已存在 %-24s %6.1f MB" % (n, os.path.getsize(fp) / 1e6))
        continue
    url = "https://hf-mirror.com/%s/resolve/main/%s" % (REPO, n)
    t0, got = time.time(), 0
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, \
                open(fp + ".part", "wb") as out:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                out.write(b)
                got += len(b)
        os.replace(fp + ".part", fp)
        print("   ✓ %-24s %6.1f MB (%.0fs)" % (n, got / 1e6, time.time() - t0))
    except Exception as e:
        print("   ✗ %s: %s" % (n, e))
        sys.exit(1)

# ---------- ② torchaudio 正确重采样出 16k 样例 ----------
print()
print("=== ② 用 torchaudio 重采样出 16kHz 样例 ===")
idx = json.loads(io.open(os.path.join(ASSETS, "voice/index.json"), encoding="utf-8").read())
truth, name = None, None
for t, f in idx["index"]["murasame"].items():
    if "本座等你好久了" in t:
        truth, name = t, f
        break
src = os.path.join(ASSETS, "voice", "murasame", name)
code = (
    "import wave, numpy as np\n"
    "from scipy.signal import resample_poly\n"
    "w = wave.open(r'%s', 'rb')\n"
    "n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()\n"
    "raw = w.readframes(n); w.close()\n"
    "x = np.frombuffer(raw, dtype='<i2').astype(np.float32)\n"
    "if ch == 2: x = x.reshape(-1, 2).mean(axis=1)\n"
    "from math import gcd\n"
    "g = gcd(sr, 16000)\n"
    "y = resample_poly(x, 16000 // g, sr // g)\n"
    "y = np.clip(y, -32768, 32767).astype('<i2')\n"
    "o = wave.open(r'%s', 'wb')\n"
    "o.setnchannels(1); o.setsampwidth(2); o.setframerate(16000); o.writeframes(y.tobytes()); o.close()\n"
    "print('resampled', sr, '->', 16000, 'samples', len(y))\n"
) % (src, os.path.join(d, "selftest.wav"))
r = subprocess.run([PY, "-c", code], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600)
print("   " + ((r.stdout or "") + (r.stderr or "")).strip()[-200:])
io.open(os.path.join(CHAT, "..", "AIpet-Murasame-main", "dev", "scripts", "_stt_truth.txt"),
        "w", encoding="utf-8").write(truth)
print("   真值:", truth, " 样例:", os.path.getsize(os.path.join(d, "selftest.wav")), "B")

# ---------- ③ OnlineAsr 内部换成 OfflineRecognizer + SenseVoice ----------
print()
print("=== ③ 改写 OnlineAsr（对外 API 不变）===")
NEW = '''package com.aipet.murasame.ui

import android.content.Context
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineSenseVoiceModelConfig
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * 离线语音识别：sherpa-onnx **非流式 SenseVoice**（int8 约 239MB，中/英/日/韩/粤）。
 *
 * 换模型历史：最初是 streaming-zipformer-zh-14M（tiny 级，效果一般）→ bilingual zipformer（流式，
 * 喂整段会出现重复）→ 现在 SenseVoice（非流式）。App 的流程是"录完再识别"，非流式更合适。
 *
 * 对外 API 与之前完全一致（init / recognizeWav / selfTest），调用方无需改动。
 * 模型放在 assets/asr-sensevoice/，首次使用时复制到 filesDir —— sherpa 需要真实文件路径。
 */
object OnlineAsr {
    private const val DIR = "asr-sensevoice"
    private const val MODEL = "model.int8.onnx"
    private const val TOK = "tokens.txt"

    @Volatile private var recognizer: OfflineRecognizer? = null
    @Volatile private var failed = false

    private fun log(ctx: Context, msg: String) = runCatching {
        File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "live2d.log")
            .appendText("[asr] " + msg + "\\n")
    }.let { }

    /** 把 assets 里的模型复制到 filesDir（只做一次），返回模型目录。 */
    private fun ensureFiles(ctx: Context): File? = runCatching {
        val dir = File(ctx.filesDir, DIR)
        if (!dir.exists()) dir.mkdirs()
        for (n in listOf(MODEL, TOK)) {
            val f = File(dir, n)
            if (!f.exists() || f.length() == 0L) {
                ctx.assets.open("$DIR/$n").use { ins -> f.outputStream().use { ins.copyTo(it) } }
            }
        }
        dir
    }.getOrElse {
        log(ctx, "ensureFiles failed: " + it.javaClass.simpleName + " " + it.message)
        null
    }

    /** 初始化识别器（幂等）。 */
    fun init(ctx: Context): Boolean {
        recognizer?.let { return true }
        if (failed) return false
        val dir = ensureFiles(ctx) ?: run { failed = true; return false }
        return runCatching {
            val cfg = OfflineRecognizerConfig(
                featConfig = FeatureConfig(sampleRate = 16000, featureDim = 80),
                modelConfig = OfflineModelConfig(
                    senseVoice = OfflineSenseVoiceModelConfig(
                        model = File(dir, MODEL).absolutePath,
                        language = "auto",
                        useInverseTextNormalization = true,
                    ),
                    tokens = File(dir, TOK).absolutePath,
                    numThreads = 2,
                    modelType = "sense_voice",
                ),
                decodingMethod = "greedy_search",
            )
            recognizer = OfflineRecognizer(config = cfg)
            log(ctx, "recognizer ready (SenseVoice int8, offline)")
            true
        }.getOrElse {
            failed = true
            log(ctx, "init failed: " + it.javaClass.simpleName + " " + it.message)
            false
        }
    }

    /** 读 16kHz/16bit/单声道 WAV → FloatArray（自带解析，不依赖第三方）。 */
    private fun readWav(path: String): FloatArray {
        val bytes = File(path).readBytes()
        var pos = 12
        var dataOff = -1
        var dataLen = 0
        while (pos + 8 <= bytes.size) {
            val id = String(bytes, pos, 4, Charsets.US_ASCII)
            val sz = ByteBuffer.wrap(bytes, pos + 4, 4).order(ByteOrder.LITTLE_ENDIAN).int
            if (id == "data") { dataOff = pos + 8; dataLen = sz; break }
            pos += 8 + sz + (sz and 1)
        }
        if (dataOff < 0) return FloatArray(0)
        val n = (minOf(dataLen, bytes.size - dataOff)) / 2
        val bb = ByteBuffer.wrap(bytes, dataOff, n * 2).order(ByteOrder.LITTLE_ENDIAN)
        return FloatArray(n) { bb.short / 32768.0f }
    }

    /** 识别一个 WAV 文件，返回文字（失败返回空串）。 */
    fun recognizeWav(ctx: Context, path: String): String {
        if (!init(ctx)) return ""
        val r = recognizer ?: return ""
        return runCatching {
            val s = readWav(path)
            if (s.isEmpty()) return@runCatching ""
            val stream = r.createStream()
            stream.acceptWaveform(s, 16000)
            r.decode(stream)
            val text = r.getResult(stream).text
            stream.release()
            text
        }.getOrElse {
            log(ctx, "recognize failed: " + it.javaClass.simpleName + " " + it.message)
            ""
        }
    }

    /** 自测：把 assets 里的 selftest.wav 复制出来识别，结果写日志。 */
    fun selfTest(ctx: Context) {
        runCatching {
            val f = File(ctx.filesDir, "selftest.wav")
            // 每次都从 assets 重新复制：换了模型/样例后，旧的 filesDir/selftest.wav 会让自检失真
            ctx.assets.open("$DIR/selftest.wav").use { ins -> f.outputStream().use { ins.copyTo(it) } }
            val t = recognizeWav(ctx, f.absolutePath)
            log(ctx, "selftest text=[" + t + "]")
        }.onFailure { log(ctx, "selftest failed: " + it.javaClass.simpleName + " " + it.message) }
    }
}
'''
io.open(ONLINE, "w", encoding="utf-8", newline="\n").write(NEW)
print("   ✓ 已改写（DIR=%s，OfflineRecognizer + SenseVoice）" % NEWDIR)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:230])
if r.returncode != 0:
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   APK %.1f MB" % (os.path.getsize(APK) / 1e6))
rr = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装:", ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:60])
