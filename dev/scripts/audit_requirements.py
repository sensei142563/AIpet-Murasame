# -*- coding: utf-8 -*-
"""① 把 requirements.txt 逐条对照项目 venv，找出"声明了但没装"的依赖
   ② 安装缺失项（默认走清华镜像）
   ③ 装完复验 comtypes/UIA
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

# 包名 → import 名（只有不一致的才需要写）
IMPORT_NAME = {
    "pyqt5": "PyQt5", "opencv-python": "cv2", "live2d-py": "live2d",
    "faster_whisper": "faster_whisper", "faster-whisper": "faster_whisper",
    "pyopengl": "OpenGL", "pillow": "PIL", "pycryptodome": "Crypto",
    "websocket-client": "websocket", "comtypes": "comtypes", "pilk": "pilk",
    "pynput": "pynput", "soundfile": "soundfile", "sounddevice": "sounddevice",
    "bitsandbytes": "bitsandbytes", "modelscope": "modelscope", "peft": "peft",
    "transformers": "transformers", "insightface": "insightface",
    "onnxruntime": "onnxruntime", "qrcode": "qrcode", "pygame": "pygame",
    "rich": "rich", "numpy": "numpy", "requests": "requests", "aiohttp": "aiohttp",
    "uvicorn": "uvicorn", "fastapi": "fastapi", "pydantic": "pydantic",
}

reqs = []
for line in io.open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8", errors="replace"):
    s = line.strip()
    if not s or s.startswith("#"):
        continue
    m = re.match(r"^([A-Za-z0-9_.\-]+)", s)
    if m:
        reqs.append(m.group(1))

PROBE = "import importlib,sys\nbad=[]\nfor n in sys.argv[1:]:\n" \
        "    try: importlib.import_module(n)\n" \
        "    except Exception as e: bad.append(n)\n" \
        "print('MISSING:' + ','.join(bad))\n"

p = os.path.join(ROOT, "dev", "scripts", "_probe_deps.py")
io.open(p, "w", encoding="utf-8", newline="\n").write(PROBE)

imports = [IMPORT_NAME.get(r.lower(), r.replace("-", "_")) for r in reqs]
r = subprocess.run([VENV, p] + imports, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600)
out = ((r.stdout or "") + (r.stderr or ""))
missing_imports = []
for l in out.splitlines():
    if l.startswith("MISSING:"):
        missing_imports = [x for x in l[8:].split(",") if x]

rev = {}
for pkg, imp in zip(reqs, imports):
    rev.setdefault(imp, []).append(pkg)
missing_pkgs = []
for imp in missing_imports:
    missing_pkgs.extend(rev.get(imp, [imp]))

print("=== requirements.txt 共 %d 条；项目 venv 里缺 %d 条 ===" % (len(reqs), len(missing_pkgs)))
for x in missing_pkgs:
    print("   ✗ " + x)

if missing_pkgs:
    print()
    print("=== 开始安装（清华镜像）===")
    cmd = [VENV, "-m", "pip", "install", "-i", MIRROR, "--disable-pip-version-check"] + missing_pkgs
    r2 = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=1800)
    tail = ((r2.stdout or "") + (r2.stderr or "")).splitlines()
    for l in tail[-12:]:
        print("   " + l.strip()[:150])
    print("   pip 退出码 =", r2.returncode)
else:
    print("   （没有缺失）")

print()
print("=== 复验：UIA 能不能用了 ===")
r3 = subprocess.run([VENV, os.path.join(ROOT, "tool", "uia.py")], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=300, cwd=ROOT)
for l in ((r3.stdout or "") + (r3.stderr or "")).splitlines()[-8:]:
    print("   " + l.strip()[:140])
