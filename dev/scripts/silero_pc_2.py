# -*- coding: utf-8 -*-
"""补 import wave 后跑完反向用例（静音/响亮纯音/方波噪声/旧探针），
   然后把 Silero 接进 tool/vad.py 成为首选（能量法兜底），最后提交。"""
import io
import math
import os
import re
import subprocess
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SHOTS = os.path.join(MAIN, "dev", "shots")
MAP = os.path.join(MAIN, "dev", "merge-map")
sys.path.insert(0, MAIN)
from tool import silero_vad, vad as energy_vad  # noqa: E402


def write_wav(path, xs, sr=16000):
    import array
    a = array.array("h", [max(-32768, min(32767, int(v * 32767))) for v in xs])
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(a.tobytes())


SIL = os.path.join(SHOTS, "vad_silence.wav")
TONE = os.path.join(SHOTS, "vad_loudtone.wav")
NOISE = os.path.join(SHOTS, "vad_noise.wav")
PROBE = os.path.join(SHOTS, "gate_probe.wav")
write_wav(SIL, [0.0002 * (1 if i % 2 == 0 else -1) for i in range(16000)])
write_wav(TONE, [0.3 * math.sin(2 * math.pi * 300 * i / 16000) for i in range(16000)])
write_wav(NOISE, [0.25 * (1 if (i // 8) % 2 == 0 else -1) for i in range(16000)])

print("=== 反向用例：Silero vs 能量法（同一段音频）===")
print("   %-26s %-46s | %s" % ("素材", "Silero", "能量法"))
cases = [("纯静音", SIL), ("响亮纯音 300Hz（死穴）", TONE), ("方波噪声", NOISE), ("旧探针嗡嗡声", PROBE)]
sil_ok = True
for label, p in cases:
    rs = silero_vad.analyze_file(p)
    xs, sr = energy_vad.read_wav_mono(p)
    re_ = energy_vad.analyze(xs, sr)
    print("   %-26s %-46s | %s" % (label, rs["detail"], re_.describe()))
    if rs["is_speech"]:
        sil_ok = False
print()
print("判定:", "✓ Silero 把静音/纯音/噪声全部正确拒绝（能量法在这些上会误判）" if sil_ok
      else "✗ 有误判")

print()
print("=== 把 Silero 接成 tool/vad.py 的首选（能量法兜底）===")
V = os.path.join(MAIN, "tool", "vad.py")
t = io.open(V, encoding="utf-8").read().replace("\r\n", "\n")
if "silero_vad" in t:
    print("· 已接")
else:
    t = t.replace('''def frame_rms(samples, frame_len):''',
                  '''def analyze_smart(path):
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


def frame_rms(samples, frame_len):''', 1)
    io.open(V, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ tool/vad.py 增加 analyze_smart()")

# /stt 改为用 analyze_smart（一处替换，保持原有早退逻辑）
API = os.path.join(MAIN, "api.py")
s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
old = """    _mono, _sr = _vad.read_wav_mono(stt_path)
    _res = _vad.analyze(_mono, _sr)
    vad_info = _res.describe()
    if not _res.is_speech:
        return {"text": "", "ms": int((time.time() - t0) * 1000),
                "reason": "vad_no_speech", "vad": vad_info}
    trimmed_path = stt_path + ".trim.wav"
    _got = _vad.trim_wav(stt_path, trimmed_path, _res, sample_rate=16000)"""
new = """    # 首选 Silero（真模型），不可用时回退能量法；两者同一组阈值
    _sp, _s0, _s1, vad_info = _vad.analyze_smart(stt_path)
    if not _sp:
        return {"text": "", "ms": int((time.time() - t0) * 1000),
                "reason": "vad_no_speech", "vad": vad_info}
    trimmed_path = stt_path + ".trim.wav"
    _got = _vad.trim_range(stt_path, trimmed_path, _s0, _s1, sample_rate=16000)"""
if old in s:
    s = s.replace(old, new, 1)
    io.open(API, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ /stt 改用 analyze_smart + trim_range")
else:
    print("⚠ 未命中 /stt 现有 VAD 段")

# 补 trim_range（按采样区间裁剪，供 analyze_smart 用）
t = io.open(V, encoding="utf-8").read().replace("\r\n", "\n")
if "def trim_range(" not in t:
    t = t.replace("def trim_wav(", '''def trim_range(src_path, dst_path, start_sample, end_sample, sample_rate=16000):
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


def trim_wav(''', 1)
    io.open(V, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ tool/vad.py 增加 trim_range / read_wav_16k_like")

print()
print("=== 语法检查 ===")
for f in (V, API):
    r = subprocess.run([sys.executable, "-c",
                        "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % f],
                       capture_output=True, text=True)
    print("   %-10s %s" % (os.path.basename(f), "✓" if r.returncode == 0 else "✗ " + (r.stderr or "")[:200]))

print()
print("=== 端到端：重启 api 后用真实语音与噪声分别打 /stt ===")
import socket
import time
import urllib.request
import json
for line in subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout.splitlines():
    if ":28565" in line and "LISTENING" in line:
        p = line.split()[-1]
        if p.isdigit():
            subprocess.run(["taskkill", "/F", "/PID", p], capture_output=True)
            print("   停旧 api", p)
time.sleep(2)
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["TYPESAFE_BASE_URL"] = "http://127.0.0.1:8765/api/evaluate"
subprocess.Popen([sys.executable, "-u", "-m", "uvicorn", "api:app", "--host", "0.0.0.0",
                  "--port", "28565"], cwd=MAIN,
                 stdout=open(os.path.join(MAIN, "dev", "logs", "api.log"), "ab"),
                 stderr=subprocess.STDOUT, env=env, creationflags=0x00000008 | 0x00000200)
for i in range(25):
    time.sleep(2)
    try:
        with socket.create_connection(("127.0.0.1", 28565), timeout=1):
            print("   ✓ 就绪 %ds" % (i * 2 + 2)); break
    except Exception:
        pass

voice = os.path.join(CHAT, "app/src/main/assets/voice/murasame")
vw = sorted(f for f in os.listdir(voice) if f.endswith(".wav"))[:1]
for label, path in (("她的真实语音", os.path.join(voice, vw[0]) if vw else None),
                    ("响亮纯音（能量法死穴）", TONE),
                    ("旧探针嗡嗡声", PROBE)):
    if not path:
        continue
    data = io.open(path, "rb").read()
    req = urllib.request.Request("http://127.0.0.1:28565/stt", data=data,
                                 headers={"Content-Type": "application/octet-stream"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            b = json.loads(r.read().decode("utf-8", "replace"))
        print("   %-22s → %.1fs %s" % (label, time.time() - t0,
                                       json.dumps(b, ensure_ascii=False)[:150]))
    except Exception as e:
        print("   %-22s → ✗ %s" % (label, str(e)[:90]))
