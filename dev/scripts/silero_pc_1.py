# -*- coding: utf-8 -*-
"""PC 侧 Silero VAD（onnxruntime，与手机同一颗模型、同一组阈值）+ 用真实语音验证。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MODEL = os.path.join(CHAT, "app/src/main/assets/vad/silero_vad.onnx")

io.open(os.path.join(MAIN, "tool", "silero_vad.py"), "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""Silero VAD（PC 侧，onnxruntime）—— 与手机端 ui/SileroVad.kt **同一颗模型、同一组阈值**。

模型契约（实测 onnxruntime 得到，不是猜的）：
    输入  x [1,512] float32, h [2,1,64] float32, c [2,1,64] float32
    输出  prob [1,1] float32, new_h, new_c
⇒ 这是 silero **v4** 形态（v5 的记忆是 128）；窗口 512 采样、要求 16kHz 单声道。

判定与手机端一致：threshold=0.5 起、min_speech=0.20s 才算说话、
min_silence=0.25s 才算结束（滞回），从而对"很大的纯音"也能正确判为非语音。
"""
import os
import wave

__all__ = ["available", "speech_prob_stream", "analyze", "describe"]

_MODEL = r"%MODEL%"
_SESS = None
_WINDOW = 512
_SR = 16000
THRESHOLD = 0.5
MIN_SPEECH_S = 0.20
MIN_SILENCE_S = 0.25


def available():
    if not os.path.isfile(_MODEL):
        return False
    try:
        import onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def _session():
    global _SESS
    if _SESS is None:
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.inter_op_num_threads = 1
        so.intra_op_num_threads = 1
        _SESS = ort.InferenceSession(_MODEL, sess_options=so, providers=["CPUExecutionProvider"])
    return _SESS


def read_wav_16k(path):
    """读 WAV → (float 列表, 采样率)。非 16k 时用线性插值重采样（silero 只吃 16k）。"""
    with wave.open(path, "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError("只支持 16bit PCM")
    import array
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if ch > 1:
        xs = [sum(a[i * ch:(i + 1) * ch]) / ch / 32768.0 for i in range(len(a) // ch)]
    else:
        xs = [v / 32768.0 for v in a]
    if sr == _SR:
        return xs, sr
    # 线性重采样到 16k
    ratio = _SR / float(sr)
    out_len = int(len(xs) * ratio)
    out = []
    for i in range(out_len):
        pos = i / ratio
        i0 = int(pos)
        i1 = min(i0 + 1, len(xs) - 1)
        frac = pos - i0
        out.append(xs[i0] * (1 - frac) + xs[i1] * frac)
    return out, _SR


def speech_prob_stream(xs):
    """逐窗返回概率列表（可单独用来画曲线/调阈值）。"""
    import numpy as np
    sess = _session()
    h = np.zeros((2, 1, 64), dtype=np.float32)
    c = np.zeros((2, 1, 64), dtype=np.float32)
    probs = []
    for i in range(0, len(xs), _WINDOW):
        chunk = xs[i:i + _WINDOW]
        if len(chunk) < _WINDOW:
            chunk = chunk + [0.0] * (_WINDOW - len(chunk))
        x = np.asarray([chunk], dtype=np.float32)
        prob, h, c = sess.run(None, {"x": x, "h": h, "c": c})
        probs.append(float(prob[0][0]))
    return probs


def analyze(xs, sample_rate=None):
    """滞回判定：连续 >=min_speech 超过 threshold 才算说话；之后连续 >=min_silence 低于阈值才算结束。"""
    if not xs:
        return {"is_speech": False, "start": 0, "end": 0, "speech_ms": 0, "detail": "空输入"}
    probs = speech_prob_stream(xs)
    win_ms = _WINDOW * 1000.0 / _SR
    need_speech = max(1, int(MIN_SPEECH_S * 1000 / win_ms))
    need_silence = max(1, int(MIN_SILENCE_S * 1000 / win_ms))
    start = end = -1
    run = 0
    sil = 0
    for i, p in enumerate(probs):
        if start < 0:
            run = run + 1 if p >= THRESHOLD else 0
            if run >= need_speech:
                start = max(0, i - run + 1)
        else:
            sil = sil + 1 if p < THRESHOLD else 0
            if sil >= need_silence:
                end = i - sil + 1
                break
    if start >= 0 and end < 0:
        end = len(probs)
    peak = max(probs) if probs else 0.0
    is_speech = start >= 0 and (end - start) * win_ms >= MIN_SPEECH_S * 1000 * 0.8
    return {
        "is_speech": is_speech,
        "start": start if start > 0 else 0,
        "end": (end if end > 0 else 0) * _WINDOW,
        "speech_ms": int(max(0, (end - start)) * win_ms) if start >= 0 else 0,
        "peak": round(peak, 4),
        "detail": "Silero%s peak=%.3f windows=%d speechMs=%d" % (
            "命中" if is_speech else "未命中", peak, len(probs),
            int(max(0, (end - start)) * win_ms) if start >= 0 else 0),
    }


def analyze_file(path):
    xs, sr = read_wav_16k(path)
    r = analyze(xs, sr)
    r["samples"] = len(xs)
    r["sr"] = sr
    return r


def describe(r):
    return r.get("detail", "?")
'''.replace("%MODEL%", MODEL.replace("\\", "\\\\")))
print("✓ 新增 tool/silero_vad.py（模型路径已写入）")

print()
print("=== 用真实语音 + 合成噪声验证这颗模型 ===")
sys.path.insert(0, MAIN)
from tool import silero_vad  # noqa: E402

print("   available:", silero_vad.available())


def show(label, path):
    try:
        r = silero_vad.analyze_file(path)
        print("   %-34s %-52s is_speech=%s" % (label, r["detail"], r["is_speech"]))
        return r["is_speech"]
    except Exception as e:
        print("   %-34s ✗ %s: %s" % (label, type(e).__name__, str(e)[:60]))
        return None


voice_dir = os.path.join(CHAT, "app/src/main/assets/voice/murasame")
wavs = sorted(f for f in os.listdir(voice_dir) if f.endswith(".wav"))[:4] if os.path.isdir(voice_dir) else []
speech_ok = []
for w in wavs:
    speech_ok.append(show("她的真实语音 " + w[:14], os.path.join(voice_dir, w)))

import math


def write_wav(path, xs, sr=16000):
    import array
    a = array.array("h", [max(-32768, min(32767, int(v * 32767))) for v in xs])
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(a.tobytes())


tmp = os.path.join(MAIN, "dev", "shots")
sil = [0.0002 * (1 if i % 2 == 0 else -1) for i in range(16000)]
write_wav(os.path.join(tmp, "vad_silence.wav"), sil)
loud = [0.3 * math.sin(2 * math.pi * 300 * i / 16000) for i in range(16000)]
write_wav(os.path.join(tmp, "vad_loudtone.wav"), loud)
noise = [0.25 * (1 if (i // 8) % 2 == 0 else -1) for i in range(16000)]
write_wav(os.path.join(tmp, "vad_noise.wav"), noise)

r_sil = show("纯静音", os.path.join(tmp, "vad_silence.wav"))
r_tone = show("响亮纯音 300Hz（能量法的死穴）", os.path.join(tmp, "vad_loudtone.wav"))
r_noise = show("方波噪声", os.path.join(tmp, "vad_noise.wav"))
r_probe = show("上一轮那个嗡嗡声探针", os.path.join(tmp, "gate_probe.wav"))

print()
ok = (all(speech_ok) and speech_ok) and (r_sil is False) and (r_tone is False) and (r_noise is False)
print("判定:", "✓ 真实语音全部命中、静音/纯音/噪声全部正确拒绝（这正是能量法做不到的）"
      if ok else "✗ 有不符预期的项，见上表")
