# -*- coding: utf-8 -*-
"""① 打印 run.py 的 _probe_f5tts / start_f5tts_api 原文
   ② **照它的逻辑实测**：逐个候选解释器跑 import f5_tts，看谁过、谁不过、各自报什么
   （不 import run.py —— 它在模块级会 re-exec venv，不能随便 import）
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① run.py 的探测与启动代码（原样）===")
ls = io.open(os.path.join(ROOT, "run.py"), encoding="utf-8", errors="replace").read().split("\n")
for i in range(607, 682):
    if i < len(ls):
        print("   %5d| %s" % (i + 1, ls[i].rstrip()[:116]))

print()
print("=== ② 照它那样实测每个候选 ===")
cands = []
try:
    from tool.paths import venv_python          # noqa
    p = venv_python()
    if p:
        cands.append(("tool.paths.venv_python", p))
except Exception as e:
    print("   （tool.paths.venv_python 取不到：%s）" % e)
cands.append(("sys.executable（我这里就是脚本用的 python）", sys.executable))
for name in ("python", "python3"):
    wp = shutil.which(name)
    if wp and all(wp != c[1] for c in cands):
        cands.append(("shutil.which(%s)" % name, wp))
try:
    r = subprocess.run(["py", "-3", "-c", "import sys;print(sys.executable)"],
                       capture_output=True, text=True, timeout=15, encoding="utf-8",
                       errors="replace")
    out = (r.stdout or "").strip().splitlines()
    pp = out[-1].strip() if (r.returncode == 0 and out) else ""
    if pp and os.path.exists(pp) and all(pp != c[1] for c in cands):
        cands.append(("py -3", pp))
except Exception:
    pass

print("   候选顺序（与 run.py 一致）：")
for i, (tag, p) in enumerate(cands, 1):
    print("      %d) %-38s %s" % (i, tag, p))

print()
print("   逐个测 import f5_tts：")
for tag, p in cands:
    if not (p and os.path.isfile(p)):
        print("      %-38s ✗ 文件不存在" % tag[:38])
        continue
    t0 = time.time()
    r = subprocess.run([p, "-c", "import f5_tts"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    dt = time.time() - t0
    err = ((r.stderr or "") + (r.stdout or "")).strip().split("\n")
    tail = " / ".join(x.strip() for x in err[-2:])[:118] if err else ""
    verdict = "✓ 能用" if r.returncode == 0 else "✗ 不行"
    print("      %-38s %s  (%.1fs)  %s" % (tag[:38], verdict, dt, tail))

print()
print("=== ③ 再确认全局那个能完整 import（不只是 f5_tts）===")
GLOBAL = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
code = ("from f5_tts.api import F5TTS\n"
        "import torch\n"
        "print('OK  f5_tts.api 可用 / torch', torch.__version__)\n")
r = subprocess.run([GLOBAL, "-c", code], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-6:]:
    if l.strip():
        print("   " + l.strip()[:130])
print("   退出码 =", r.returncode)
