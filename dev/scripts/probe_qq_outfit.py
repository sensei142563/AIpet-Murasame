# -*- coding: utf-8 -*-
"""核 deck 第 15 页那句「QQ 侧立绘与桌宠同一套装扮」是否成立。
   思路：找 QQ 侧发图的地方，看它用的装扮来源是不是与桌宠同一份数据
        （data/portrait_choice.json 或 pets/<id>/... 的装扮状态）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git|dev\\)", re.I)

print("=== ① 装扮状态的存取点（portrait_choice / 装扮）===")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        try:
            ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(ls, 1):
            if "portrait_choice" in l:
                print("   %-40s %5d| %s" % (p.replace(ROOT + "\\", "")[:40], i, l.strip()[:96]))

print()
print("=== ② QQ 发图那条链（谁生成/发送 QQ 侧立绘）===")
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        try:
            ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(ls, 1):
            if re.search(r"send_image|send_group|qq_.*image|generate_fgimage|fgimage|立绘", l) \
                    and re.search(r"qq|QQ|群|发送|generate_fgimage", l):
                print("   %-40s %5d| %s" % (p.replace(ROOT + "\\", "")[:40], i, l.strip()[:96]))
