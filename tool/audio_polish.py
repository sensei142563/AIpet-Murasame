# -*- coding: utf-8 -*-
"""合成语音的后处理：统一响度 + 给偏闷的结果轻度提亮。

为什么需要（实测：同一句话 × 6 种情绪参考音频）
----------------------------------------------
    情绪    参考高频占比   合成高频占比   合成 RMS
    害羞      0.155        0.176        0.073   ← 气声参考，合成也闷、还最小声
    高兴      0.297        0.269        0.062   ← 也最小声
    生气      0.259        0.359        0.156

音色跟着参考音频走（模型正常行为），但**响度差 2.6 倍（≈8dB）**、**高频占比差 2 倍**，
听感就是"有时清晰、有时发闷、有时太小"。这里只做两件保守的事：

    1) 响度：RMS 低于目标就整体增益（最多 +9dB）；**高于目标不动**（不做压限，保住动态）
    2) 亮度：3kHz 以上能量占比低于阈值时才做高架提升（约 +5.6dB）；本身够亮的不动

只用标准库 + numpy（没装 numpy、不是 16bit PCM、太短、任何异常 → **原样返回**，
绝不影响出声）。排查用：`python -m tool.audio_polish <某个.wav>` 看处理前后的数据。

⚠ 使用边界：**同一段音频只处理一次**（产品里是"合成完立刻处理一次"）。判据是"高频占比"，
所以对**近乎纯音**的信号（例如整段只有一个低频正弦）每次调用都会再提亮一次 —— 真实语音
里辅音/气声会让占比超过阈值，第二次就自然不动了；但纯音/静音这种退化输入不要反复喂进来。
"""
from __future__ import annotations

import io
import os
import struct
import sys
import wave

TARGET_RMS = 0.130        # 目标响度（实测 6 种情绪的中间偏亮值）
MAX_GAIN = 2.8            # 最多放大 2.8 倍（≈+9dB），再多会把底噪抬起来
HF_LOW = 0.22             # 高频占比低于这个值算"闷"
HF_BOOST = 1.9            # 高架提升倍数（≈+5.6dB）
HF_CUT = 3000.0           # 高架起点（Hz）
PEAK_LIMIT = 0.985        # 增益后的峰值上限


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def _read_wav(data: bytes):
    """→ (采样率, 声道数, 样本宽度, 浮点数组, 原始字节)  失败返回 None"""
    try:
        w = wave.open(io.BytesIO(data), "rb")
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
        w.close()
        if sw != 2:
            return None                      # 只处理 16bit PCM（GPT-SoVITS / F5-TTS 输出就是）
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


def measure(data: bytes) -> dict:
    """量一下这段 wav（响度 RMS / 峰值 / >3kHz 高频占比），排查与自测用；失败返回 {}"""
    got = _read_wav(data)
    if got is None:
        return {}
    import numpy as np
    sr, ch, sw, a, _raw = got
    x = a.reshape(-1).astype(np.float32) if a.ndim > 1 else a.astype(np.float32)
    if len(x) == 0:
        return {}
    out = {"sr": sr, "ch": ch, "n": int(len(x)),
           "rms": float(np.sqrt((x ** 2).mean())),
           "peak": float(np.abs(x).max())}
    try:
        sp = np.fft.rfft(x)
        fr = np.fft.rfftfreq(len(x), 1.0 / sr)
        out["hf"] = float(np.abs(sp)[fr > HF_CUT].sum() / max(1e-9, np.abs(sp).sum()))
    except Exception:
        out["hf"] = 0.0
    return out


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
    #   ⚠ 留 0.5% 容差（≈0.04dB，听不出来）：否则第一次处理完的 RMS 是 0.12996，
    #     第二次仍算"低于目标"→ 又写一遍文件（polish_wav_file 会被判成"有改动"）。
    rms = float(np.sqrt((x ** 2).mean()))
    gain = 1.0
    if rms > 1e-6 and rms < target_rms * 0.995:
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
        return data                                  # 本来就够响够亮 → 一个字节都不动
    try:
        if ch > 1:
            x = x.reshape(-1, ch)
        return _write_wav(sr, ch, sw, x)
    except Exception:
        return data


def polish_wav_file(path: str, target_rms: float = TARGET_RMS) -> bool:
    """就地处理一个 wav 文件；返回是否真的改了（读不到/处理失败返回 False）"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        out = polish_wav_bytes(data, target_rms)
        if out is data or out == data:
            return False
        tmp = path + ".polish.tmp"
        with open(tmp, "wb") as f:
            f.write(out)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        _say("用法: python -m tool.audio_polish <某个.wav> [目标RMS]")
        raise SystemExit(0)
    p = sys.argv[1]
    tgt = float(sys.argv[2]) if len(sys.argv) > 2 else TARGET_RMS
    with open(p, "rb") as f:
        raw = f.read()
    before = measure(raw)
    out = polish_wav_bytes(raw, tgt)
    after = measure(out)
    _say("处理前: RMS=%.4f 峰值=%.4f 高频占比=%.3f" % (before.get("rms", -1),
                                                   before.get("peak", -1),
                                                   before.get("hf", -1)))
    _say("处理后: RMS=%.4f 峰值=%.4f 高频占比=%.3f" % (after.get("rms", -1),
                                                   after.get("peak", -1),
                                                   after.get("hf", -1)))
    _say("字节数: %d → %d%s" % (len(raw), len(out), "" if raw != out else "（未改动）"))
