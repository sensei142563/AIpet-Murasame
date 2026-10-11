# -*- coding: utf-8 -*-
"""电脑端 VAD：tool/vad.py（纯 stdlib）+ 接进 /stt + 单测（含"嗡嗡声不该被识别"这条真实 bug 的回归）"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

io.open(os.path.join(MAIN, "tool", "vad.py"), "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""语音活动检测（VAD）/ 静音剔除 —— 与手机端 ui/VadGate.kt **同一套算法与同一组阈值**。

为什么两处都要：噪声会被识别模型"编"出内容（实测 whisper 把我一段合成嗡嗡声识别成
"Teksting av Nicolai Winther"）。手机端在识别前过一遍，电脑端在 /stt 入口也过一遍，
于是"手机上传的音频"和"电脑收到的音频"两头都不会被噪声骗。

算法（与 Kotlin 版一致，便于两边用同样信号对照）：
  1) 20ms 分帧算 RMS；
  2) 噪声底 = 各帧 RMS 的 20 百分位（**nearest-rank**，不插值）；
  3) 帧算有声 ⟺ rms > max(absFloor, noise × relThreshold)；
  4) 累计语音 ≥ minSpeechMs 才算真的说了话；
  5) 返回裁剪区间（含 padding）。

只依赖标准库（wave/audioop/array）。
"""
import array
import math
import wave

__all__ = ["VadResult", "analyze", "trim_wav", "read_wav_mono"]

FRAME_MS = 20
MIN_SPEECH_MS = 200
REL_THRESHOLD = 3.0
ABS_FLOOR = 0.006
PAD_MS = 150


class VadResult:
    __slots__ = ("is_speech", "start_sample", "end_sample", "speech_ms",
                 "noise_rms", "peak_rms", "frames")

    def __init__(self, is_speech, start_sample, end_sample, speech_ms, noise_rms, peak_rms, frames):
        self.is_speech = is_speech
        self.start_sample = start_sample
        self.end_sample = end_sample
        self.speech_ms = speech_ms
        self.noise_rms = noise_rms
        self.peak_rms = peak_rms
        self.frames = frames

    def describe(self):
        return "VAD%s speechMs=%d noise=%.4f peak=%.4f frames=%d" % (
            "命中" if self.is_speech else "未命中", self.speech_ms,
            self.noise_rms, self.peak_rms, self.frames)


def read_wav_mono(path):
    """读 WAV → (float 采样列表, 采样率)。多声道取平均（手机端发的是 16k 单声道）。"""
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError("只支持 16bit PCM（当前 sampwidth=%d）" % sw)
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if ch > 1:
        mono = [0.0] * (len(a) // ch)
        for i in range(len(mono)):
            s = 0.0
            for c in range(ch):
                s += a[i * ch + c]
            mono[i] = s / ch / 32768.0
    else:
        mono = [v / 32768.0 for v in a]
    return mono, sr


def frame_rms(samples, frame_len):
    if frame_len <= 0 or not samples:
        return []
    out = []
    for i in range(0, len(samples) - frame_len + 1, frame_len):
        acc = 0.0
        for j in range(i, i + frame_len):
            v = samples[j]
            acc += v * v
        out.append(math.sqrt(acc / frame_len))
    return out


def percentile(values, p):
    """nearest-rank（与 Kotlin 版一致）：噪声底宁可偏低，安全交给 abs_floor 兜底。"""
    if not values:
        return 0.0
    s = sorted(values)
    idx = int((len(s) - 1) * p)
    return s[max(0, min(idx, len(s) - 1))]


def analyze(samples, sample_rate=16000, frame_ms=FRAME_MS, min_speech_ms=MIN_SPEECH_MS,
            rel_threshold=REL_THRESHOLD, abs_floor=ABS_FLOOR, pad_ms=PAD_MS):
    frame_len = max(1, int(sample_rate * frame_ms / 1000))
    rms = frame_rms(samples, frame_len)
    if not rms:
        return VadResult(False, 0, 0, 0, 0.0, 0.0, 0)
    noise = percentile(rms, 0.20)
    gate = max(abs_floor, noise * rel_threshold)
    first = last = -1
    peak = 0.0
    for i, v in enumerate(rms):
        if v > peak:
            peak = v
        if v > gate:
            if first < 0:
                first = i
            last = i
    if first < 0:
        return VadResult(False, 0, 0, 0, noise, peak, len(rms))
    speech_ms = (last - first + 1) * frame_ms
    if speech_ms < min_speech_ms:
        return VadResult(False, 0, 0, speech_ms, noise, peak, len(rms))
    pad = int(sample_rate * pad_ms / 1000)
    s = max(0, first * frame_len - pad)
    e = min(len(samples), (last + 1) * frame_len + pad)
    return VadResult(True, s, e, speech_ms, noise, peak, len(rms))


def trim_wav(src_path, dst_path, result, sample_rate=None):
    """把 src 的语音段写成 dst（16bit 单声道 WAV）。返回写入的采样数。"""
    samples, sr = read_wav_mono(src_path)
    if sample_rate:
        sr = sample_rate
    seg = samples[result.start_sample:result.end_sample]
    if not seg:
        return 0
    a = array.array("h", [max(-32768, min(32767, int(v * 32767))) for v in seg])
    with wave.open(dst_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(a.tobytes())
    return len(a)
''')
print("✓ 新增 tool/vad.py")

# 接进 /stt
API = os.path.join(MAIN, "api.py")
s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
if "tool.vad" in s or "from tool import vad" in s:
    print("· /stt 已接 VAD")
else:
    old = """            text = await asyncio.to_thread(_stt_transcribe_full, tmp.name)"""
    new = """            # 先过 VAD：没说话就别让模型去"编"（实测嗡嗡声会被 whisper 识别成一句丹麦语）
            vad_info = "skipped"
            try:
                from tool import vad as _vad
                mono, sr = _vad.read_wav_mono(tmp.name)
                res = _vad.analyze(mono, sr)
                vad_info = res.describe()
                if not res.is_speech:
                    return {"text": "", "ms": int((time.time() - t0) * 1000),
                            "reason": "vad_no_speech", "vad": vad_info}
                # 只把语音段送去识别（省算力、减少边缘幻觉）
                trimmed = tmp.name + ".trim.wav"
                got = _vad.trim_wav(tmp.name, trimmed, res, sample_rate=16000)
                if got > 0:
                    tmp.name = trimmed       # finally 会一并清理
                    vad_info += " trimmed=%d" % got
            except Exception as _e:
                vad_info = "vad error: %s: %s" % (type(_e).__name__, _e)
            text = await asyncio.to_thread(_stt_transcribe_full, tmp.name)"""
    if old in s:
        s = s.replace(old, new, 1)
        s = s.replace("""            return {"text": text or "", "ms": int((time.time() - t0) * 1000), "engine": "faster-whisper-large-v3"}""",
                      """            return {"text": text or "", "ms": int((time.time() - t0) * 1000),
                    "engine": "faster-whisper-large-v3", "vad": vad_info}""", 1)
        io.open(API, "w", encoding="utf-8", newline="\n").write(s)
        print("✓ /stt 已接 VAD（无语音直接返回 vad_no_speech）")
    else:
        print("✗ 未命中 /stt 锚点")
        sys.exit(1)

# 单测
TEST = os.path.join(MAIN, "dev", "scripts", "test_vad.py")
io.open(TEST, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""VAD 单测：与 Kotlin 版同信号、同期望（含"嗡嗡声不该被识别"的真实 bug 回归）。"""
import array
import io
import math
import os
import sys
import wave

sys.path.insert(0, r"E:\\university\\order\\python\\pet\\AIpet-Murasame-main")
from tool import vad  # noqa: E402

SR = 16000
ok = True


def note(m, c):
    global ok
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        ok = False


def silence(ms, amp=0.0005):
    n = int(SR * ms / 1000)
    return [amp * (1 if i % 2 == 0 else -1) for i in range(n)]


def tone(ms, amp, freq=440.0):
    n = int(SR * ms / 1000)
    return [amp * math.sin(2 * math.pi * freq * i / SR) for i in range(n)]


def concat(*parts):
    out = []
    for p in parts:
        out += p
    return out


print("=== 与 Kotlin 版同样的场景 ===")
r = vad.analyze(silence(1000), SR)
note("纯静音不算说话（%s）" % r.describe(), not r.is_speech)

sig = concat(silence(400), tone(600, 0.25), silence(400))
r = vad.analyze(sig, SR)
note("静音中的 600ms 突发算说话（%s）" % r.describe(), r.is_speech and 560 <= r.speech_ms <= 700)
seg = sig[r.start_sample:r.end_sample]
note("裁剪后短于原信号、长于语音本身（%d < %d < %d）" % (len(seg), len(sig), len(seg)), 0 < len(seg) < len(sig))

r = vad.analyze(concat(silence(300), tone(60, 0.4), silence(300)), SR)
note("60ms 咔哒被拒（speechMs=%d）" % r.speech_ms, (not r.is_speech) and r.speech_ms == 60)

r = vad.analyze(tone(1500, 0.2, 300.0), SR)
note("持续大声噪声不误判（noise=%.4f peak=%.4f）" % (r.noise_rms, r.peak_rms), not r.is_speech)

sig = concat(tone(500, 0.01, 220.0), tone(500, 0.2, 440.0), tone(500, 0.01, 220.0))
r = vad.analyze(sig, SR)
note("底噪上的语音被检出（%s）" % r.describe(), r.is_speech and 450 <= r.speech_ms <= 600)

note("百分位 nearest-rank：%s" % vad.percentile([0.01, 0.02, 0.03, 0.5, 0.9], 0.2),
     abs(vad.percentile([0.01, 0.02, 0.03, 0.5, 0.9], 0.2) - 0.01) < 1e-6)
note("空输入安全", not vad.analyze([], SR).is_speech)

print()
print("=== 真实 bug 回归：上一轮那个嗡嗡声探针 ===")
probe = r"E:\\university\\order\\python\\pet\\AIpet-Murasame-main\\dev\\shots\\gate_probe.wav"
if os.path.isfile(probe):
    mono, sr = vad.read_wav_mono(probe)
    r = vad.analyze(mono, sr)
    note("那段的 VAD 判定：%s" % r.describe(), True)
    note("⇒ 它会被 /stt 以 vad_no_speech 拦下（而不是被识别成一句丹麦语）", not r.is_speech)
else:
    note("探针 wav 不存在（跳过）", True)

print()
print("总结:", "电脑端 VAD 行为与手机端一致 ✓" if ok else "有失败项 ✗")
sys.exit(0 if ok else 1)
''')
print("✓ 新增 dev/scripts/test_vad.py")

print()
print("=== 跑单测 ===")
r = subprocess.run([PY, "-u", TEST], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600)
print((r.stdout or "")[-1800:])
if r.returncode != 0:
    print((r.stderr or "")[-600:])
    sys.exit(1)
