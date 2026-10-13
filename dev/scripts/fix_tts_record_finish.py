# -*- coding: utf-8 -*-
"""收尾：
  ① 纠正现有 data/tts_model.json 里互换的两个标签（这是运行时缓存，改它可省掉下次的白重启）
  ② 加一条**源码守卫**（防止有人改回 _extra[1]/_extra[3] 的下标写法）
  ③ 跑全套自检
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

# ---------- ① 修缓存文件 ----------
F = os.path.join(ROOT, "data", "tts_model.json")
if os.path.isfile(F):
    d = json.load(io.open(F, encoding="utf-8", errors="replace"))
    g, s = str(d.get("gpt") or ""), str(d.get("sovits") or "")
    if g.lower().endswith(".pth") and s.lower().endswith(".ckpt"):
        d["gpt"], d["sovits"] = s, g
        io.open(F, "w", encoding="utf-8", newline="\n").write(
            json.dumps(d, ensure_ascii=False, indent=1))
        print("✓ ① 已纠正 data/tts_model.json 的标签：gpt ← %s，sovits ← %s" % (s, g))
        print("     （原来 gpt=%s / sovits=%s，正好写反）" % (g, s))
    elif g.lower().endswith(".ckpt") and s.lower().endswith(".pth"):
        print("· ① 文件里的标签看着已经是对的（gpt=%s / sovits=%s），不动" % (g, s))
    else:
        print("· ① 后缀不像 GPT(.ckpt)/SoVITS(.pth)，不敢猜，不动：gpt=%r sovits=%r" % (g, s))
else:
    print("· ① 没有 data/tts_model.json（下次启动会重新写）")

# ---------- ② 源码守卫 ----------
TF = os.path.join(ROOT, "tests", "test_config_contracts.py")
t = io.open(TF, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
GUARD = '''

# ── 语音服务记录（data/tts_model.json）的标签方向必须与命令行标志一致 ──
# 背景（2026-10-13 实测修过）：run.py 曾按下标取值 —— `_extra = ["-s", <soVITS>, "-g", <GPT>]`
# 却写 `"gpt": _extra[1]`、`"sovits": _extra[3]`，两个标签**互换**。
# 而 tool/tts_service.py 正是拿这两个字段判断"要不要重启语音服务"，
# want 侧标签正确、have 侧互换 ⇒ **永远判为不一致** ⇒ 每次预载都杀掉服务重载模型，
# 表现为那个 GPT-SoVITS 终端反复出现。已改为按 -s / -g 标志取值。
_g = io.open(os.path.join(REPO, "run.py"), encoding="utf-8", errors="replace").read()
check("run.py 用 _flag_arg 取 -g / -s（不再按下标）",
      '_flag_arg(_extra, "-g")' in _g and '_flag_arg(_extra, "-s")' in _g)
check("run.py 不再出现 _extra[1] / _extra[3] 当 gpt/sovits 用",
      '"gpt": os.path.basename(_extra[1])' not in _g
      and '"sovits": os.path.basename(_extra[3])' not in _g)
'''
if "语音服务记录（data/tts_model.json）的标签方向" not in t:
    t = t.rstrip() + GUARD
    io.open(TF, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ② 已给 tests/test_config_contracts.py 加 2 条守卫")
else:
    print("· ② 已有守卫")

# ---------- ③ 全套 ----------
print()
print("=== ③ 全套自检 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-5:]:
    print("   " + l.strip()[:130])
