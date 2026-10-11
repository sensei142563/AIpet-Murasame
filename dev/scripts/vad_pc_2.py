# -*- coding: utf-8 -*-
"""用正则按原缩进插入 VAD；用单独变量传路径（不改 tmp.name）；跑单测。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
API = os.path.join(MAIN, "api.py")
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
TEST = os.path.join(MAIN, "dev", "scripts", "test_vad.py")

s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
if "tool import vad" in s or "from tool import vad" in s:
    print("· 已接 VAD")
else:
    pat = re.compile(r"^(?P<ind>[ \t]*)text = await asyncio\.to_thread\(_stt_transcribe_full, tmp\.name\)\s*$",
                     re.M)
    m = pat.search(s)
    if not m:
        print("✗ 仍找不到调用行")
        sys.exit(1)
    ind = m.group("ind")
    ins = ("{i}# 先过 VAD：没说话就别让模型去\"编\"（实测嗡嗡声会被 whisper 识别成一句丹麦语）\n"
           "{i}vad_info = \"skipped\"\n"
           "{i}stt_path = tmp.name\n"
           "{i}trimmed_path = None\n"
           "{i}try:\n"
           "{i}    from tool import vad as _vad\n"
           "{i}    _mono, _sr = _vad.read_wav_mono(stt_path)\n"
           "{i}    _res = _vad.analyze(_mono, _sr)\n"
           "{i}    vad_info = _res.describe()\n"
           "{i}    if not _res.is_speech:\n"
           "{i}        return {{\"text\": \"\", \"ms\": int((time.time() - t0) * 1000),\n"
           "{i}                \"reason\": \"vad_no_speech\", \"vad\": vad_info}}\n"
           "{i}    trimmed_path = stt_path + \".trim.wav\"\n"
           "{i}    _got = _vad.trim_wav(stt_path, trimmed_path, _res, sample_rate=16000)\n"
           "{i}    if _got > 0:\n"
           "{i}        stt_path = trimmed_path          # 只把语音段送去识别（省算力、减少边缘幻觉）\n"
           "{i}        vad_info += \" trimmed=%d\" % _got\n"
           "{i}except Exception as _e:\n"
           "{i}    vad_info = \"vad error: %s: %s\" % (type(_e).__name__, _e)\n"
           "{i}text = await asyncio.to_thread(_stt_transcribe_full, stt_path)").format(i=ind)
    s = s[:m.start()] + ins + s[m.end():]
    # 返回体带上 vad 摘要
    s = s.replace("""return {"text": text or "", "ms": int((time.time() - t0) * 1000), "engine": "faster-whisper-large-v3"}""",
                  """return {"text": text or "", "ms": int((time.time() - t0) * 1000),
                    "engine": "faster-whisper-large-v3", "vad": vad_info}""", 1)
    # finally 里一并清理裁剪文件
    s = s.replace("""            try:
                os.unlink(tmp.name)
            except Exception:
                pass""",
                  """            try:
                os.unlink(tmp.name)
            except Exception:
                pass
            try:
                if trimmed_path:
                    os.unlink(trimmed_path)
            except Exception:
                pass""", 1)
    io.open(API, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已按原缩进插入 VAD（缩进=%d 空格）" % len(ind))

print()
r = subprocess.run([PY, "-c", "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % API],
                   capture_output=True, text=True)
print("   语法: " + ("✓ OK" if r.returncode == 0 else "✗ " + (r.stderr or "")[:300]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 跑 VAD 单测 ===")
r2 = subprocess.run([PY, "-u", TEST], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=600)
print((r2.stdout or "")[-2000:])
if r2.returncode != 0:
    print((r2.stderr or "")[-600:])
    sys.exit(1)
