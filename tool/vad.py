# -*- coding: utf-8 -*-
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


def analyze_smart(path):
    """首选 Silero（真模型，能区分"大纯音"与"说话"），不可用时回退能量法。

    返回 (is_speech, start_sample, end_sample, detail)。start/end 是按 **16k** 计的采样位置，
    方便调用方直接裁 WAV。
    """
    try:
        from tool import silero_vad as _sv
        if _sv.available():
            r = _sv.analyze_file(path)
            return (bool(r["is_speech"]), int(r["start"]), int(r["end"]), r["detail"])
    except Exception as e:
        _err = "%s: %s" % (type(e).__name__, e)
    else:
        _err = "Silero 不可用（缺 onnxruntime 或模型）"
    samples, sr = read_wav_mono(path)
    r = analyze(samples, sr)
    return (bool(r.is_speech), r.start_sample, r.end_sample,
            r.describe() + "（回退能量法：%s）" % _err)


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


def trim_range(src_path, dst_path, start_sample, end_sample, sample_rate=16000):
    """按【16k 采样区间】裁剪写盘（analyze_smart 的返回就是这个坐标系）。"""
    samples, sr = read_wav_16k_like(src_path)
    n_src = len(samples)
    if sr != sample_rate and sr > 0:
        k = float(sample_rate) / sr
        start_sample = int(start_sample / k)
        end_sample = int(end_sample / k)
    s0 = max(0, min(start_sample, n_src))
    s1 = max(s0, min(end_sample, n_src))
    seg = samples[s0:s1]
    if not seg:
        return 0
    import array
    a = array.array("h", [max(-32768, min(32767, int(v * 32767))) for v in seg])
    with wave.open(dst_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sample_rate); w.writeframes(a.tobytes())
    return len(a)


def read_wav_16k_like(path):
    """读 WAV 为 float（原采样率，不做重采样），供 trim_range 用。"""
    import array as _array
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError("只支持 16bit PCM")
    a = _array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if ch > 1:
        return [sum(a[i * ch:(i + 1) * ch]) / ch / 32768.0 for i in range(len(a) // ch)], sr
    return [v / 32768.0 for v in a], sr


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
