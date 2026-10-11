# -*- coding: utf-8 -*-
"""VAD 单测：与 Kotlin 版同信号、同期望（含"嗡嗡声不该被识别"的真实 bug 回归）。"""
import math
import os
import sys

sys.path.insert(0, r"E:\university\order\python\pet\AIpet-Murasame-main")
from tool import vad  # noqa: E402

SR = 16000
ok = True


def note(m, c):
    global ok
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        ok = False


def silence(ms, amp=0.0005):
    return [amp * (1 if i % 2 == 0 else -1) for i in range(int(SR * ms / 1000))]


def tone(ms, amp, freq=440.0):
    return [amp * math.sin(2 * math.pi * freq * i / SR) for i in range(int(SR * ms / 1000))]


def concat(*parts):
    out = []
    for p in parts:
        out += p
    return out


print("=== 与 Kotlin 版同样的场景（同阈值同算法）===")
r = vad.analyze(silence(1000), SR)
note("纯静音不算说话（%s）" % r.describe(), not r.is_speech)

sig = concat(silence(400), tone(600, 0.25), silence(400))
r = vad.analyze(sig, SR)
note("静音中的 600ms 突发算说话（%s）" % r.describe(), r.is_speech and 560 <= r.speech_ms <= 700)
seg = sig[r.start_sample:r.end_sample]
note("裁剪后短于原信号（%d < %d）" % (len(seg), len(sig)), 0 < len(seg) < len(sig))

r = vad.analyze(concat(silence(300), tone(60, 0.4), silence(300)), SR)
note("60ms 咔哒被拒（speechMs=%d）" % r.speech_ms, (not r.is_speech) and r.speech_ms == 60)

r = vad.analyze(tone(1500, 0.2, 300.0), SR)
note("持续大声噪声不误判（noise=%.4f peak=%.4f）" % (r.noise_rms, r.peak_rms), not r.is_speech)

sig = concat(tone(500, 0.01, 220.0), tone(500, 0.2, 440.0), tone(500, 0.01, 220.0))
r = vad.analyze(sig, SR)
note("底噪上的语音被检出（%s）" % r.describe(), r.is_speech and 450 <= r.speech_ms <= 600)

p = vad.percentile([0.01, 0.02, 0.03, 0.5, 0.9], 0.2)
note("百分位 nearest-rank = %.4f（与 Kotlin 一致）" % p, abs(p - 0.01) < 1e-6)
note("空输入安全", not vad.analyze([], SR).is_speech)

print()
print("=== 真实 bug 回归：上一轮那个嗡嗡声探针 ===")
probe = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots\gate_probe.wav"
if os.path.isfile(probe):
    mono, sr = vad.read_wav_mono(probe)
    r = vad.analyze(mono, sr)
    print("      %s" % r.describe())
    note("VAD 判定为无语音 ⇒ /stt 会以 vad_no_speech 拦下（而不是识别成一句丹麦语）", not r.is_speech)
else:
    note("探针 wav 不存在（跳过）", True)

print()
print("总结:", "电脑端 VAD 行为与手机端一致 ✓" if ok else "有失败项 ✗")
sys.exit(0 if ok else 1)
