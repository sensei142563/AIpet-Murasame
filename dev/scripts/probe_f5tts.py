# -*- coding: utf-8 -*-
"""查 F5-TTS 为什么缺包：
  ① 谁在跑 longtext/f5tts_server.py（run.py 用哪个解释器 / 长文本服务怎么起）
  ② 两个解释器（runtime\venv vs 全局 Python310）里 f5_tts / pypinyin 有没有
  ③ 这两个包在磁盘上到底存不存在（可能装到了第三个地方）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
GLOBAL = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
DOTVENV = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

print("=== ① 长文本服务是怎么起的（run.py / longtext 里的启动代码）===")
for rel in ("run.py", "longtext/f5tts_server.py", "longtext/longtext_tts.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"f5tts_server|_project_python|sys\.executable|sys\.executable|Popen|"
                     r"python_path|9881|F5TTS_DEVICE|f5_tts|pypinyin", l):
            print("   %-26s %5d| %s" % (rel, i, l.strip()[:108]))

print()
print("=== ② 三个解释器里有没有 f5_tts / pypinyin ===")
for tag, py in (("runtime\\venv", VENV), ("全局 Python310", GLOBAL), (".venv", DOTVENV)):
    print("   --- %s ---" % tag)
    print("       ", py, "存在" if os.path.isfile(py) else "✗ 不存在")
    if not os.path.isfile(py):
        continue
    code = ("import importlib.util as u\n"
            "for m in ('f5_tts','pypinyin','torch','soundfile','torchaudio'):\n"
            "    s = u.find_spec(m)\n"
            "    print('   %-12s %s' % (m, '有' if s else '缺'))\n"
            "import sys; print('   Python', sys.version.split()[0], sys.executable)\n")
    r = subprocess.run([py, "-c", code], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
        if l.strip():
            print("    " + l.strip()[:120])

print()
print("=== ③ 磁盘上有没有 f5_tts / pypinyin 的安装痕迹 ===")
import glob  # noqa: E402
pats = [
    r"E:\university\order\python\pet\AIpet-Murasame-main\runtime\venv\Lib\site-packages\f5_tts*",
    r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\Lib\site-packages\f5_tts*",
    r"E:\university\order\python\pet\AIpet-Murasame-main\.venv\Lib\site-packages\f5_tts*",
    r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\Lib\site-packages\pypinyin*",
    r"E:\university\order\python\pet\AIpet-Murasame-main\runtime\venv\Lib\site-packages\pypinyin*",
]
for pat in pats:
    hits = glob.glob(pat)
    print("   %-96s %s" % (pat.replace("C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310", "<global>")
                          .replace(ROOT, "<root>")[:96], ("有 %d 个" % len(hits)) if hits else "无"))

print()
print("=== ④ f5tts_server.py 里对缺包的提示（看它期望怎么装）===")
p = os.path.join(ROOT, "longtext", "f5tts_server.py")
if os.path.isfile(p):
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"f5-tts|pip install|未安装|pypinyin|F5TTS_v1_Base|vocos", l):
            print("   %5d| %s" % (i, l.strip()[:110]))
