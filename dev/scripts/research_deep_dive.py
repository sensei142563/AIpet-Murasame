# -*- coding: utf-8 -*-
"""深挖参考实现：
  ① AnimaFlux：架构文档 + 衰减/边界的具体参数（半衰期、上下界、字段表）
  ② memobase：检索/记忆怎么存（embeddings？episodic？）
  ③ graphiti：时序知识图谱的检索入口（search.py 有哪些检索模式）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REF = r"E:\university\order\research-refs"


def dump(path, max_lines=90, pat=None, ctx=0):
    if not os.path.isfile(path):
        print("   （缺文件 %s）" % path)
        return
    ls = io.open(path, encoding="utf-8", errors="replace").read().split("\n")
    print("   ── %s（%d 行）" % (os.path.relpath(path, REF), len(ls)))
    if pat is None:
        for l in ls[:max_lines]:
            print("      " + l.rstrip()[:112])
        if len(ls) > max_lines:
            print("      …（还有 %d 行）" % (len(ls) - max_lines))
    else:
        n = 0
        for i, l in enumerate(ls, 1):
            if re.search(pat, l, re.I):
                for j in range(max(0, i - 1 - ctx), min(len(ls), i + ctx)):
                    print("      %5d| %s" % (j + 1, ls[j].rstrip()[:108]))
                n += 1
                if n >= max_lines:
                    break


A = os.path.join(REF, "animaflux")
print("=== ① AnimaFlux 结构 ===")
for dp, dn, fn in os.walk(A):
    if ".git" in dp:
        continue
    rel = os.path.relpath(dp, A)
    for f in sorted(fn):
        if f.endswith((".py", ".md", ".toml")):
            p = os.path.join(dp, f)
            print("   %8.1f KB  %s" % (os.path.getsize(p) / 1024,
                                       os.path.join(rel, f).replace("\\", "/")[:96]))
print()
print("=== ①-a docs/architecture.md ===")
dump(os.path.join(A, "docs", "architecture.md"), 70)
print()
print("=== ①-b 衰减/边界参数（在源码里找 half_life / decay / bound）===")
for dp, dn, fn in os.walk(A):
    if ".git" in dp:
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        if re.search(r"half_life|decay|bound", t, re.I):
            print("   ── %s" % os.path.relpath(p, A))
            for i, l in enumerate(t.split("\n"), 1):
                if re.search(r"half_life|HALF_LIFE|decay|max_delta|min_delta|bound", l, re.I):
                    s = l.strip()
                    if s and not s.startswith("#"):
                        print("      %5d| %s" % (i, s[:106]))

print()
print("=== ② memobase：检索怎么做的 ===")
M = os.path.join(REF, "memobase")
dump(os.path.join(M, "README.md"), 60, pat=r"search|retriev|embed|vector|profile|episod", ctx=0)
print()
dump(os.path.join(M, "assets", "episodic_memory.py"), 40)

print()
print("=== ③ graphiti：检索模式 ===")
G = os.path.join(REF, "graphiti")
dump(os.path.join(G, "graphiti_core", "search", "search.py"), 45,
     pat=r"class |def |SearchConfig|reranker|MMR|bm25|cosine|node_distance|episode", ctx=0)
