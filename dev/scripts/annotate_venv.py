# -*- coding: utf-8 -*-
"""按主人要求：把"虚拟环境"这件事**重点注释**清楚，免得反复搞混。
   ⚠ 关键事实（主人 2026-10-14 明确 + 本机实测）：
     本机**不用虚拟环境**，依赖都装在**全局 Python 310**；`runtime\\venv` 是历史遗留、包不全。
   同时**如实记录矛盾**：run.py 原注释说的恰好相反（"必须用 venv"），
   那是历史上的情况；不写清楚的话，下一个人（包括我）还会踩。
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
RUN = os.path.join(ROOT, "run.py")

BANNER = '''# ══════════════════════════════════════════════════════════════════════════════
# ⚠⚠⚠ 重点：本机的「虚拟环境」约定（2026-10-14 主人明确 + 本机实测）
#
#   主人原话：
#     「咱本地不用虚拟环境」
#     「咱们都是全局 Python，都用 GPU 加速」
#
#   ⇒ **本机跑项目用的是全局 Python 3.10**（C:\\Users\\ASUS\\AppData\\Local\\Programs\\
#      Python\\Python310\\python.exe），依赖（torch / f5_tts / pypinyin / onnxruntime …）
#      都装在**全局**的 site-packages 里。
#   ⇒ `runtime\\venv` 是**历史遗留**，里面的包**不全**（实测：有 torch，但 f5_tts、
#      pypinyin 都没有）。**默认不要用它** —— 用了就会报 "No module named 'xxx'"。
#
#   ⚠ 与下面代码注释的矛盾（如实记录，别被带偏）：
#      本文件 `_ensure_project_python` / `_project_python` / `_f5tts_venv_python`
#      三个函数的注释都说"必须用 runtime\\venv，否则会崩（MSVCP140 / 抢 28565 端口）"。
#      那是**历史上的情况**（当年依赖确实装在 venv 里）。
#      现在反了：依赖在全局，venv 反而缺包。
#      ⇒ 以本条为准；那三处函数**保留原行为**（改了有崩的风险），
#        但调用它们的地方要注意：**凡是需要 f5_tts/新依赖的子进程，必须用全局 Python**
#        （F5-TTS 那次就是这么修的：探到能用的解释器后，启动时要用**探到的那个**，
#          而不是再写死 venv —— 见 start_f5tts_api 里 2026-10-14 的注释）。
#
#   📄 详细说明另见：docs/本机环境约定-不用虚拟环境.md
# ══════════════════════════════════════════════════════════════════════════════


'''

t = io.open(RUN, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "本机的「虚拟环境」约定" in t:
    print("· 已经注释过了")
else:
    # 插到文件最前面的 import 之后（第 7 行 import time 之后）
    anchor = "import json\nimport time\n"
    if anchor in t:
        t = t.replace(anchor, anchor + "\n\n" + BANNER.rstrip() + "\n", 1)
        io.open(RUN, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ run.py 顶部已加「本机虚拟环境约定」重点注释")
    else:
        print("✗ 锚点未命中（import 段）")
        sys.exit(1)

# 在三个函数处各补一行指针
POINTERS = [
    ('def _ensure_project_python():',
     'def _ensure_project_python():\n'
     '    # ⚠ 本机约定见文件顶部「虚拟环境」注释：**本机不用 venv**；\n'
     '    #   这个函数仍会把解释器切到 runtime\\venv（历史行为，暂不改，改了有崩的风险）。'),
    ('def _project_python() -> str:',
     'def _project_python() -> str:\n'
     '    # ⚠ 本机约定见文件顶部：**本机不用 venv**（依赖在全局）。此函数保留历史行为。'),
    ('def _f5tts_venv_python():',
     'def _f5tts_venv_python():\n'
     '    # ⚠ 本机约定见文件顶部：**本机不用 venv**。\n'
     '    #   名字虽然叫 venv，但 2026-10-14 起 F5-TTS 已改为用**探测到的**解释器\n'
     '    #   （见 start_f5tts_api），不再无条件用它。'),
]
for old, new in POINTERS:
    if old in t and "本机约定见文件顶部" not in t.split(old, 1)[1][:200]:
        t = t.replace(old, new, 1)
        print("✓ 已加指针：%s" % old[:42])
    else:
        print("· 跳过（已有或未命中）：%s" % old[:42])
io.open(RUN, "w", encoding="utf-8", newline="\n").write(t)

try:
    py_compile.compile(RUN, doraise=True)
    print("✓ py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

print()
print("=== 复核（前 45 行）===")
for i, l in enumerate(io.open(RUN, encoding="utf-8", errors="replace").read().split("\n")[:45], 1):
    print("   %4d| %s" % (i, l.rstrip()[:112]))
