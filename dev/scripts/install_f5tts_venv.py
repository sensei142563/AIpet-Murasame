# -*- coding: utf-8 -*-
"""把 f5_tts / pypinyin 装进 runtime\\venv（项目实际用的解释器）。
   ⚠ 必须 --no-deps：f5-tts 默认会拉 torch 等一大堆，可能把现有 GPU 环境换掉。
      所以只装它自己，然后逐个补它真正缺的小依赖。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
PY = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(args, timeout=1800, show=14):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV, timeout=timeout)
    lines = ((r.stdout or "") + (r.stderr or "")).split("\n")
    for l in lines[-show:]:
        if l.strip():
            print("      " + l.strip()[:130])
    return r.returncode, (r.stdout or "") + (r.stderr or "")


print("=== ① 装之前：venv 里 torch 版本（留证据，装完对比）===")
run([PY, "-c", "import torch;print('torch', torch.__version__, 'cuda', torch.version.cuda)"], 300, 4)

print()
print("=== ② 只装 f5-tts + pypinyin（--no-deps，不碰 torch）===")
rc, out = run([PY, "-m", "pip", "install", "--no-deps", "f5-tts", "pypinyin",
               "--no-warn-script-location"], 1800, 18)
print("      退出码 =", rc)

print()
print("=== ③ 装之后：torch 有没有被动过 ===")
run([PY, "-c", "import torch;print('torch', torch.__version__, 'cuda', torch.version.cuda)"], 300, 4)

print()
print("=== ④ 试着 import f5_tts（看还缺什么依赖）===")
code = ("import f5_tts, sys\n"
        "print('f5_tts OK', f5_tts.__file__)\n"
        "from f5_tts.api import F5TTS\n"
        "print('F5TTS 类 OK')\n")
rc2, out2 = run([PY, "-c", code], 600, 10)
print("      退出码 =", rc2)

print()
print("=== ⑤ 缺哪个装哪个（只装列出来的小包，仍不带 torch）===")
import re  # noqa: E402
miss = re.findall(r"No module named '([^']+)'", out2 or "")
miss = [m for m in dict.fromkeys(miss) if not m.startswith(("torch", "f5_tts"))]
print("      缺失模块：", miss or "（无）")
# 有些 import 名与 pip 名不同，做个最小映射
PIPNAME = {"yaml": "pyyaml", "PIL": "pillow", "cv2": "opencv-python", "sklearn": "scikit-learn",
           "vocos": "vocos", "einops": "einops", "transformers": "transformers",
           "soundfile": "soundfile", "librosa": "librosa", "pypinyin": "pypinyin",
           "cn2an": "cn2an", "torchaudio": "torchaudio", "numpy": "numpy",
           "omegaconf": "omegaconf", "ema_pytorch": "ema-pytorch", "rotary_embedding_torch":
           "rotary-embedding-torch", "accelerate": "accelerate", "tqdm": "tqdm",
           "jieba": "jieba", "pydub": "pydub", "matplotlib": "matplotlib", "pandas": "pandas"}
pkgs = [PIPNAME.get(m, m) for m in miss]
if pkgs:
    print("      对应 pip 包：", pkgs)
    rc3, _ = run([PY, "-m", "pip", "install", "--no-deps"] + pkgs +
                 ["--no-warn-script-location"], 1800, 12)
    print("      退出码 =", rc3)
    print()
    print("=== ⑥ 再试一次 import ===")
    rc4, _ = run([PY, "-c", code], 600, 10)
    print("      退出码 =", rc4)
else:
    print("      （没有缺失，直接可 import）")
