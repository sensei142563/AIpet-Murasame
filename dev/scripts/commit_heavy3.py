# -*- coding: utf-8 -*-
"""提交闸门的真实接口级取证；并记录 whisper 噪声幻觉这一观察。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """test(tts): 重型闸门的真实接口级取证（并发两个 /stt 实测串行）

用 /stt（原始 WAV body，单条 26 秒的真重活）做端到端取证，而不是只看单元测试：
  · 并发发起两个 /stt，第二个在第一个进行中发出；
  · 期间每 0.5s 轮询 /heavy/status。

实测：
  请求1 → 200，耗时 26.27s
  请求2 → 200，耗时 26.79s，但**自身只跑了 1.0s**（ms=1023）—— 其余时间在等闸门
  闸门观测：busy 采样 41/41，占用者 ['stt']，最大等待数 1
  历史记录：[{stt, 26784ms, 19:01:21}, {stt, 26240ms, 19:01:20}] ⇒ 两次串行、无重叠

附：探针是一段合成的嗡嗡声，却被 whisper 识别成 "Teksting av Nicolai Winther" ——
这是 whisper 对噪声的典型幻觉。结论：送进 STT 的音频需要 VAD/静音剔除，
否则"没说话"也会被识别出一句莫名其妙的话（对语音唤醒/连续识别尤其重要）。
已记入文档，作为后续 STT 改进项。

顺带说明：/tts 实测是 GPT-SoVITS 代理（转发到 localhost:9880），
当前 9880 未运行 ⇒ 用 /tts 做取证会得到 422/上游失败，故改用 /stt。
"""
p = os.path.join(MAP, "_msg_heavy3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
print()
print("=== 本轮相关文件 ===")
for f in ("tool/heavy_gate.py", "dev/scripts/test_heavy_gate.py",
          "dev/scripts/heavy_gate_e2e2.py", "api.py"):
    p2 = os.path.join(MAIN, f.replace("/", os.sep))
    print("   %-42s %s %d B" % (f, "✓" if os.path.isfile(p2) else "✗",
                                os.path.getsize(p2) if os.path.isfile(p2) else 0))
