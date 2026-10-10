# -*- coding: utf-8 -*-
"""查：表情包判断与 Jev 调用写在哪个函数里、聊天实际走的是哪条路径。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame"
PAT = re.compile(r"(JevClient|parseStickers|useSticker|stickerNames|fun chat\(|ChatCore|"
                 r"stickersAvailable|biaoqingbao|fun reply|streamReply|chatOnce)")

for dp, ds, fs in os.walk(BASE):
    for f in sorted(fs):
        if not f.endswith(".kt"):
            continue
        p = os.path.join(dp, f)
        L = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        hits = [(i, l) for i, l in enumerate(L, 1) if PAT.search(l)]
        if hits:
            print("--- %s ---" % os.path.relpath(p, BASE))
            for i, l in hits[:26]:
                print("   %5d| %s" % (i, l.strip()[:116]))
