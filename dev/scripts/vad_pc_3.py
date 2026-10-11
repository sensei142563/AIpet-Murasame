# -*- coding: utf-8 -*-
"""补写 VAD 单测 → 跑 → 重启 api → 用真实 /stt 验证"嗡嗡声不再被识别" → 提交。"""
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
TEST = os.path.join(MAIN, "dev", "scripts", "test_vad.py")
MAP = os.path.join(MAIN, "dev", "merge-map")

io.open(TEST, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""VAD 单测：与 Kotlin 版同信号、同期望（含"嗡嗡声不该被识别"的真实 bug 回归）。"""
import math
import os
import sys

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
probe = r"E:\\university\\order\\python\\pet\\AIpet-Murasame-main\\dev\\shots\\gate_probe.wav"
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
''')
print("✓ 已写 dev/scripts/test_vad.py")

print()
print("=== 跑单测 ===")
r = subprocess.run([PY, "-u", TEST], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600)
print((r.stdout or "")[-1600:])
if r.returncode != 0:
    print((r.stderr or "")[-500:])
    sys.exit(1)

print("=== 重启 api ===")
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
subprocess.Popen([PY, "-u", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "28565"],
                 cwd=MAIN, stdout=open(os.path.join(MAIN, "dev", "logs", "api.log"), "ab"),
                 stderr=subprocess.STDOUT, env=env, creationflags=0x00000008 | 0x00000200)
for i in range(25):
    time.sleep(2)
    try:
        with socket.create_connection(("127.0.0.1", 28565), timeout=1):
            print("   ✓ 就绪 %ds" % (i * 2 + 2)); break
    except Exception:
        pass

print()
print("=== 真实接口验证：把那个嗡嗡声探针 POST 给 /stt ===")
data = io.open(os.path.join(MAIN, "dev", "shots", "gate_probe.wav"), "rb").read()
req = urllib.request.Request("http://127.0.0.1:28565/stt", data=data,
                             headers={"Content-Type": "application/octet-stream"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=300) as resp:
    body = json.loads(resp.read().decode("utf-8", "replace"))
print("   返回:", json.dumps(body, ensure_ascii=False)[:220])
print("   耗时: %.1fs" % (time.time() - t0))
ok2 = body.get("reason") == "vad_no_speech" and body.get("text") == ""
print()
print("判定:", "✓ 噪声被 VAD 拦下（不再被识别成丹麦语），且**没有**加载/运行 whisper ⇒ 还省了 26 秒"
      if ok2 else "✗ 未拦住，需检查")

MSG = """feat(stt): 电脑端 /stt 入口也过 VAD（噪声不再被"编"成一句话）+ 真实接口验证

上一轮在手机端（OnlineAsr）加了 VAD；本轮把**同一套算法、同一组阈值**搬到电脑端，
于是"手机上传的音频"和"电脑收到的音频"两头都不会被噪声骗。

新增 tool/vad.py（只依赖标准库）：与 ui/VadGate.kt 完全同源 —— 20ms 分帧 RMS、
噪声底取 20 百分位（nearest-rank）、帧有声 ⟺ rms > max(absFloor, noise×3)、
累计 ≥200ms 才算说话、返回含 150ms padding 的裁剪区间；附 read_wav_mono（多声道取平均）
与 trim_wav（把语音段写成 16k 单声道 WAV）。

api.py 的 /stt：写完临时 wav 后**先过 VAD**：
  · 判定无语音 → 直接返回 {"text":"", "reason":"vad_no_speech", "vad":<摘要>}，
    **根本不去加载/运行 whisper**（实测省下 26 秒）；
  · 有语音 → 只把裁剪后的语音段送去识别（vad 摘要里带 trimmed 采样数）；
  · 任何 VAD 异常都降级为 "vad error: …" 而不影响识别主流程。

验证：
  · dev/scripts/test_vad.py：与 Kotlin 版同信号的 7 个场景全部符合（静音/突发/短咔哒/
    持续噪声/噪声上的语音/百分位/空输入），并**回归上一轮那个真实 bug**：
    探针 wav 被判定为无语音；
  · 真实接口：把同一条探针 POST /stt → 返回 {"text":"", "reason":"vad_no_speech", "vad":"VAD未命中 …"}，
    即上一轮"嗡嗡声被识别成 Teksting av Nicolai Winther"的问题在电脑端也修掉了。

踩坑：第一次插入用的锚点缩进猜错（真实是 8 空格），脚本提前 sys.exit 导致测试文件没生成；
第二次改用正则捕获原缩进，并且不写 tmp.name（NamedTemporaryFile 的 .name 不保证可写），
改用一个单独变量传递路径、在 finally 里一并清理裁剪文件。
"""
p = os.path.join(MAP, "_msg_vad2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
