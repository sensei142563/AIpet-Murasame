# -*- coding: utf-8 -*-
"""对比旧版（嵌套目录）与当前版的语音服务启动方式。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD = r"E:\university\order\python\pet\AIpet-Murasame-main_V1.17.2\AIpet-Murasame-main"
NEW = r"E:\university\order\python\pet\AIpet-Murasame-main"

PAT = re.compile(r'api_v2\.py|api\.py|CREATE_NEW_CONSOLE|CREATE_NO_WINDOW|_console_flags|quiet_mode|"-s"|start_recording')

for tag, root in (("旧版 V1.17.2", OLD), ("当前版", NEW)):
    print("=== %s ===" % tag)
    rp = os.path.join(root, "run.py")
    if not os.path.isfile(rp):
        print("   ✗ 没有 run.py:", rp)
        print()
        continue
    ls = io.open(rp, encoding="utf-8", errors="replace").read().split("\n")
    n = 0
    for i, l in enumerate(ls, 1):
        if PAT.search(l):
            print("   %5d| %s" % (i, l.strip()[:108]))
            n += 1
    print("   （共 %d 行命中）" % n)
    gs = os.path.join(root, "GPT-SoVITS")
    if os.path.isdir(gs):
        ents = [f for f in sorted(os.listdir(gs))
                if f in ("api.py", "api_v2.py", "webui.py", "go-webui.bat")]
        print("   GPT-SoVITS 入口:", ", ".join(ents) if ents else "（无）")
    print()

# 关键差异：旧版有没有 quiet_mode / _console_flags
print("=== 结论用的两句话对比 ===")
for tag, root in (("旧版", OLD), ("当前版", NEW)):
    rp = os.path.join(root, "run.py")
    if not os.path.isfile(rp):
        continue
    src = io.open(rp, encoding="utf-8", errors="replace").read()
    print("   %-6s quiet_mode=%s  _console_flags=%s  CREATE_NEW_CONSOLE=%s"
          % (tag, "有" if "quiet_mode" in src else "无",
             "有" if "_console_flags" in src else "无",
             "有" if "CREATE_NEW_CONSOLE" in src else "无"))
