# -*- coding: utf-8 -*-
"""读三处实现：PendingInbox 的原子写先例、MemoryStore 的读写、ChatScreen 的会话读写。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")


def show(rel, a, b, title):
    p = os.path.join(SRC, rel.replace("/", os.sep))
    lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    print("=== %s（%s 第 %d~%d 行）===" % (title, rel, a, b))
    for i in range(max(0, a - 1), min(len(lines), b)):
        print("%4d| %s" % (i + 1, lines[i].rstrip()[:140]))
    print()


show("bot/ilink/PendingInbox.kt", 70, 105, "已有原子写先例")
show("bot/chat/MemoryStore.kt", 1, 95, "记忆读写")
show("ui/ChatScreen.kt", 100, 160, "会话读写")
