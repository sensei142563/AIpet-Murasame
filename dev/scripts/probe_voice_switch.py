# -*- coding: utf-8 -*-
"""查：项目自己的代码里，有没有"换角色语音"的动作，以及怎么换的。
   只看项目代码（跳过 GPT-SoVITS 第三方目录）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD = r"E:\university\order\python\pet\AIpet-Murasame-main_V1.17.2\AIpet-Murasame-main"
NEW = r"E:\university\order\python\pet\AIpet-Murasame-main"

SKIP_DIRS = {"GPT-SoVITS", "runtime", ".venv", "site-packages", ".git",
             "_import_tmp", "dev", "docs", "NapCat.Shell.Windows.OneKey", "__pycache__"}
KEYS = ["set_gpt_weights", "set_sovits_weights", "change_gpt_sovits_weights",
        "pet_voice_weights", "gpt_weights", "sovits_weights", "voice_weights",
        "refer_wav_path", "change_refer", "/tts"]

for tag, root in (("旧版 V1.17.2", OLD), ("当前版", NEW)):
    print("=" * 70)
    print("=== %s（只看项目自己的 .py）===" % tag)
    hits = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dp, f)
            rel = p.replace(root + os.sep, "")
            try:
                ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
            except Exception:
                continue
            for i, l in enumerate(ls, 1):
                if any(k in l for k in KEYS):
                    hits.append((rel, i, l.strip()))
    for rel, i, l in hits[:34]:
        print("   %-40s %5d| %s" % (rel[:40], i, l[:88]))
    print("   （共 %d 处）" % len(hits))
    print()
