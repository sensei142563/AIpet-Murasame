# -*- coding: utf-8 -*-
"""① 读 api.py 里 /qq/queue/send 的写入方式（是否以 \n 结尾）② 据此修 qq_outbox ③ 重跑对抗"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
API = os.path.join(MAIN, "api.py")
OB = os.path.join(MAIN, "qq", "qq_outbox.py")

print("=== api.py /qq/queue/send 的实现（原文）===")
body = io.open(API, encoding="utf-8", errors="replace").read()
i = body.find('@app.post("/qq/queue/send")')
print(body[i:i + 1400])

print()
print("=== 所有写 qq_outbox 的地方（看有没有结尾换行）===")
for m in re.finditer(r"qq_outbox|outbox", body):
    seg = body[max(0, m.start() - 120):m.start() + 220]
    if "open(" in seg or ".write(" in seg:
        print("   …" + seg.replace("\n", " ")[:300])
        print("   ---")
