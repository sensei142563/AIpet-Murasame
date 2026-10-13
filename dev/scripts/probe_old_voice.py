# -*- coding: utf-8 -*-
"""查实：旧版能不能"每个角色不同声音"？当前版换 api.py 的真正原因是什么？
   ① 旧版 run.py 的 TTS 启动块（用哪个脚本、怎么传权重）
   ② 旧版有没有 pet_voice_weights / 角色级音色
   ③ 两边有没有在运行时调 /set_gpt_weights、/set_sovits_weights（api_v2 的角色切换方式）
   ④ 当前版 run.py 的完整分支 + 那段注释的原文
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD = r"E:\university\order\python\pet\AIpet-Murasame-main_V1.17.2\AIpet-Murasame-main"
NEW = r"E:\university\order\python\pet\AIpet-Murasame-main"


def block(root, fname, a, b, tag):
    p = os.path.join(root, fname)
    print("=== %s :: %s 第 %d~%d 行 ===" % (tag, fname, a, b))
    if not os.path.isfile(p):
        print("   ✗ 不存在")
        return
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i in range(max(0, a - 1), min(len(ls), b)):
        print("   %5d| %s" % (i + 1, ls[i].rstrip()[:114]))


block(OLD, "run.py", 726, 762, "旧版")
print()
block(NEW, "run.py", 905, 950, "当前版")

print()
print("=== 关键能力对照（是否存在这些字样）===")
K = ["pet_voice_weights", "set_gpt_weights", "set_sovits_weights",
     "change_gpt_sovits_weights", "sovits_path", "gpt_path", "voices/short", "voices\\\\short"]
for tag, root in (("旧版", OLD), ("当前版", NEW)):
    print("   --- %s ---" % tag)
    for f in ("run.py", "tool/tts_service.py", "tool/voices.py", "classes/murasame_class.py"):
        p = os.path.join(root, f)
        if not os.path.isfile(p):
            continue
        src = io.open(p, encoding="utf-8", errors="replace").read()
        found = [k for k in ("pet_voice_weights", "set_gpt_weights", "set_sovits_weights",
                             "change_gpt_sovits_weights") if k in src]
        if found:
            print("      %-28s %s" % (f, "、".join(found)))
