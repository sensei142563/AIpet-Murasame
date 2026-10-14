# -*- coding: utf-8 -*-
"""调研①：看 E:\\111\\--main 是个什么项目、它怎么做"记忆/数据库查找"
   调研②：顺带摸清我们现在的记忆实现（有哪些文件、有没有检索）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REF = r"E:\111\--main"
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① E:\\111\\--main 是否存在 ===")
print("   ", "存在 ✓" if os.path.isdir(REF) else "不存在 ✗")
if not os.path.isdir(REF):
    # 看看 E:\111 下有什么
    up = r"E:\111"
    if os.path.isdir(up):
        print("   E:\\111 下有：")
        for d in sorted(os.listdir(up))[:20]:
            print("      ", d)
    sys.exit(0)

print()
print("=== ② 顶层结构 ===")
n = 0
for f in sorted(os.listdir(REF)):
    p = os.path.join(REF, f)
    if os.path.isdir(p):
        cnt = sum(len(fn) for _, _, fn in os.walk(p))
        print("   [dir] %-38s %5d 个文件" % (f[:38], cnt))
    else:
        print("       %-38s %8d B" % (f[:38], os.path.getsize(p)))
    n += 1
    if n > 28:
        print("   …")
        break

print()
print("=== ③ 找与记忆/检索/数据库相关的文件 ===")
PAT = re.compile(r"memory|记忆|database|sqlite|chroma|faiss|embed|向量|检索|检索|retriev|"
                 r"knowledge|知识|storage|存储", re.I)
hits = []
for dp, dn, fn in os.walk(REF):
    if any(x in dp for x in ("\\.git", "\\node_modules", "\\__pycache__", "\\.venv", "\\venv",
                             "\\site-packages", "\\dist", "\\build")):
        continue
    for f in fn:
        if not f.endswith((".py", ".md", ".json", ".ts", ".js", ".sql", ".yaml", ".yml")):
            continue
        p = os.path.join(dp, f)
        rel = p.replace(REF + os.sep, "")
        if PAT.search(f) or PAT.search(rel):
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            hits.append((sz, rel))
hits.sort(reverse=True)
for sz, rel in hits[:40]:
    print("   %8.1f KB  %s" % (sz / 1024, rel[:104]))
print("   （共 %d 个相关文件）" % len(hits))

print()
print("=== ④ 我们现在的记忆相关文件 ===")
OURS = re.compile(r"memory|记忆|日记|journal|history|snapshot|state|attention|self_learn", re.I)
ours = []
for dp, dn, fn in os.walk(ROOT):
    if any(x in dp for x in ("\\.git", "\\GPT-SoVITS", "\\runtime", "\\_internal", "\\build",
                             "\\.venv", "\\NapCat", "\\__pycache__", "\\F5-TTS_Models",
                             "\\dev\\tts_model_cache", "\\models")):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        rel = os.path.join(dp, f).replace(ROOT + os.sep, "")
        if OURS.search(rel):
            try:
                sz = os.path.getsize(os.path.join(dp, f))
            except OSError:
                continue
            ours.append((sz, rel))
ours.sort(reverse=True)
for sz, rel in ours[:26]:
    print("   %8.1f KB  %s" % (sz / 1024, rel[:104]))
print("   （共 %d 个）" % len(ours))
