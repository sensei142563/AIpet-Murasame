# -*- coding: utf-8 -*-
"""对比 V1.17.2 旧版与当前版的"语音服务启动方式"，回答"以前那个终端为什么不一样"。
   只看三件事：① 起哪个脚本（api.py / api_v2.py）② 控制台标志 ③ quiet 开关。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD = r"E:\university\order\python\pet\AIpet-Murasame-main_V1.17.2"
NEW = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== 旧版目录是否存在 ===")
print("   ", "存在 ✓" if os.path.isdir(OLD) else "不存在 ✗", OLD)

for tag, root in (("旧版 V1.17.2", OLD), ("当前版", NEW)):
    print()
    print("=== %s ===" % tag)
    rp = os.path.join(root, "run.py")
    if not os.path.isfile(rp):
        print("   ✗ 没有 run.py")
        continue
    ls = io.open(rp, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r'api_v2\.py|api\.py|CREATE_NEW_CONSOLE|CREATE_NO_WINDOW|_console_flags|quiet_mode|"-s"', l):
            s = l.strip()
            if len(s) > 4:
                print("   %5d| %s" % (i, s[:110]))
    # GPT-SoVITS 目录里的入口脚本
    gs = os.path.join(root, "GPT-SoVITS")
    if os.path.isdir(gs):
        ents = [f for f in sorted(os.listdir(gs))
                if f in ("api.py", "api_v2.py", "webui.py", "go-webui.bat")]
        print("   GPT-SoVITS 目录入口:", ", ".join(ents) if ents else "（无）")
    else:
        print("   （没有 GPT-SoVITS 目录）")
