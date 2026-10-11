# -*- coding: utf-8 -*-
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

_MODEL = r"E:\\university\\order\\python\\pet\\chatter\\app/src/main/assets/vad/silero_vad.onnx"
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
