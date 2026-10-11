# -*- coding: utf-8 -*-
"""探测：① PC 有没有 onnxruntime ② silero_vad.onnx 的输入/输出契约 ③ 手上有没有真实语音素材。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MODEL = os.path.join(CHAT, "app/src/main/assets/vad/silero_vad.onnx")

print("=== ① Python 运行时探测 ===")
for mod in ("onnxruntime", "sherpa_onnx", "numpy"):
    try:
        m = __import__(mod)
        print("   ✓ %-14s %s" % (mod, getattr(m, "__version__", "?")))
    except Exception as e:
        print("   ✗ %-14s %s" % (mod, str(e)[:60]))

print()
print("=== ② 模型 I/O 契约 ===")
print("   模型: %s (%.2f MB)" % (MODEL, os.path.getsize(MODEL) / 1e6 if os.path.isfile(MODEL) else 0))
try:
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.inter_op_num_threads = 1
    so.intra_op_num_threads = 1
    sess = ort.InferenceSession(MODEL, sess_options=so, providers=["CPUExecutionProvider"])
    print("   输入:")
    for i in sess.get_inputs():
        print("      %-10s %-18s %s" % (i.name, i.type, i.shape))
    print("   输出:")
    for o in sess.get_outputs():
        print("      %-10s %-18s %s" % (o.name, o.type, o.shape))
except Exception as e:
    print("   ✗ 无法加载模型: %s: %s" % (type(e).__name__, str(e)[:120]))

print()
print("=== ③ 真实语音素材（她台词包里的 wav）===")
vd = os.path.join(CHAT, "app/src/main/assets/voice")
n = 0
for base, dirs, files in os.walk(vd):
    for f in sorted(files):
        if f.endswith(".wav"):
            p = os.path.join(base, f)
            print("   %-42s %7.1f KB" % (os.path.relpath(p, vd), os.path.getsize(p) / 1024))
            n += 1
            if n >= 6:
                break
    if n >= 6:
        break
print("   共找到 %d 个（只用前几个做验证）" % n)

print()
print("=== ④ 已有的合成噪声探针 ===")
probe = os.path.join(MAIN, "dev", "shots", "gate_probe.wav")
print("   %s %s" % (probe, "存在 ✓" if os.path.isfile(probe) else "不存在 ✗"))
