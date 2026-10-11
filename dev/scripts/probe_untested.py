# -*- coding: utf-8 -*-
"""读 OneBotParse 接口、记忆导入导出的实现位置（纯逻辑优先，便于单测）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAIN = os.path.join(PET, "AIpet-Murasame-main")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")

print("=== ① OneBotParse 的公开函数与数据类 ===")
p = os.path.join(SRC, "bot/chat/OneBotParse.kt")
if os.path.isfile(p):
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"^(object|data class|fun |    fun |    val |    var |internal|private fun)", l):
            print("   %4d| %s" % (i, l.strip()[:130]))
else:
    print("   ✗ 不存在")

print()
print("=== ② 记忆导出/导入：手机端相关文件 ===")
hits = []
for base, dirs, files in os.walk(SRC):
    for f in files:
        fp = os.path.join(base, f)
        try:
            body = io.open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if re.search(r"export|import|导出|导入|memory|记忆", body):
            hits.append((os.path.relpath(fp, SRC), len(body)))
for h, n in sorted(hits)[:14]:
    print("   %-56s %d B" % (h, n))

print()
print("=== ③ 电脑端（api.py / tool）里与记忆导出导入相关的函数 ===")
for base, dirs, files in os.walk(MAIN):
    if any(x in base for x in (".git", "node_modules", "dev\\shots", "dev\\tts_model_cache")):
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        fp = os.path.join(base, f)
        try:
            body = io.open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if re.search(r"def .*(export|import).*memory|记忆(导出|导入)|memory_(export|import)", body, re.I):
            rel = os.path.relpath(fp, MAIN)
            names = re.findall(r"def (\w*(?:export|import)\w*)", body, re.I)
            print("   %-46s %s" % (rel, names[:6]))

print()
print("=== ④ 现有测试文件清单（看哪些已经被覆盖）===")
td = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame")
for f in sorted(os.listdir(td)) if os.path.isdir(td) else []:
    if f.endswith(".kt"):
        body = io.open(os.path.join(td, f), encoding="utf-8", errors="replace").read()
        print("   %-26s %d 个 @Test" % (f, body.count("@Test")))
