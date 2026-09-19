# -*- coding: utf-8 -*-
"""合成语音的后处理：统一响度 + 给偏闷的结果轻度提亮。

为什么需要（实测数据，同一句话 × 6 种情绪参考）：
    情绪    参考高频占比   合成高频占比   合成 RMS
    害羞      0.155        0.176        0.073   ← 气声参考，合成也闷、还最小声
    高兴      0.297        0.269        0.062   ← 也最小声
    生气      0.259        0.359        0.156
    → 音色是跟着"参考音频"走的（模型正常行为，不是串音/语音包混用），
      但**响度差 2.6 倍（≈8dB）**、**高频占比差 2 倍**，听感就是"有时清晰有时糊"。

处理（保守，只做两件事）：
    1) 响度：RMS 低于目标就整体增益（最多 +9dB），高于目标不动（不做压限，避免破坏动态）
    2) 亮度：3kHz 以上能量占比低于阈值时才做高架提升（约 +4dB），本身够亮的不动
纯标准库 + numpy（没装 numpy 就原样返回，不影响出声）。
"""
from __future__ import annotations

import io
import struct
import wave

TARGET_RMS = 0.130        # 目标响度（实测 6 种情绪的中间偏亮值）
MAX_GAIN = 2.8            # 最多放大 2.8 倍（≈+9dB），再多会把底噪抬起来
HF_LOW = 0.22             # 高频占比低于这个值算"闷"
HF_BOOST = 1.9            # 高架提升倍数（≈+5.6dB）
HF_CUT = 3000.0           # 高架起点（Hz）
PEAK_LIMIT = 0.985        # 增益后的峰值上限


def _read_wav(data: bytes):
    """→ (采样率, 声道数, 样本宽度, 浮点数组, 原始参数)  失败返回 None"""
    try:
        w = wave.open(io.BytesIO(data), "rb")
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
        w.close()
        if sw != 2:
            return None                      # 只处理 16bit PCM（GPT-SoVITS 输出就是）
        import numpy as np
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ch > 1:
            a = a.reshape(-1, ch)
        return sr, ch, sw, a, raw
    except Exception:
        return None


def _write_wav(sr: int, ch: int, sw: int, a) -> bytes:
    import numpy as np
    if a.ndim > 1:
        a = a.reshape(-1)
    x = np.clip(a, -1.0, 1.0)
    pcm = (x * 32767.0).astype("<i2")
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(ch)
    w.setsampwidth(sw)
    w.setframerate(sr)
    w.writeframes(pcm.tobytes())
    w.close()
    return buf.getvalue()


def polish_wav_bytes(data: bytes, target_rms: float = TARGET_RMS) -> bytes:
    """统一响度 +（必要时）轻度提亮；任何异常都原样返回，保证不影响出声。"""
    if not data or data[:4] != b"RIFF":
        return data
    try:
        import numpy as np
    except Exception:
        return data
    got = _read_wav(data)
    if got is None:
        return data
    sr, ch, sw, a, _raw = got
    x = a.reshape(-1).copy() if a.ndim > 1 else a.copy()
    if len(x) < 512:
        return data

    # ① 响度（只提升，不衰减）
    rms = float(np.sqrt((x ** 2).mean()))
    gain = 1.0
    if rms > 1e-6 and rms < target_rms:
        gain = min(MAX_GAIN, target_rms / rms)

    # ② 亮度：只有偏闷才提（在频域对 >3kHz 的 bin 做增益）
    need_eq = False
    try:
        sp = np.fft.rfft(x)
        fr = np.fft.rfftfreq(len(x), 1.0 / sr)
        hf = float(np.abs(sp)[fr > HF_CUT].sum() / max(1e-9, np.abs(sp).sum()))
        need_eq = hf < HF_LOW
        if need_eq:
            sp = np.where(fr > HF_CUT, sp * HF_BOOST, sp)
            x = np.fft.irfft(sp, n=len(x)).astype(np.float32)
    except Exception:
        need_eq = False

    x = x * gain
    peak = float(np.abs(x).max()) if len(x) else 0.0
    if peak > PEAK_LIMIT:
        x = x * (PEAK_LIMIT / peak)
    if gain == 1.0 and not need_eq:
        return data                            # 本来就好，不折腾
    try:
        out = _write_wav(sr, ch, sw, x)
        return out if len(out) > 44 else data
    except Exception:
        return data


def polish_wav_file(path: str, target_rms: float = TARGET_RMS) -> bool:
    """就地处理一个 wav 文件；成功返回 True"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        out = polish_wav_bytes(data, target_rms)
        if out is data or out == data:
            return False
        with open(path, "wb") as f:
            f.write(out)
        return True
    except Exception:
        return False
