# -*- coding: utf-8 -*-
"""找 jixia-kernel 里 /retrieve 的后端实现：用什么存储与检索（SQLite FTS？向量？BM25？）"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REF = r"E:\111\--main"
PAT = re.compile(r"retrieve|top_k|fts5|sqlite|tantivy|bm25|embedding|cosine|"
                 r"index|索引|词条|mastery|review|复习", re.I)
SKIP = ("\\.git", "\\node_modules", "\\__pycache__", "\\.venv", "\\venv",
        "\\site-packages", "\\target", "\\dist", "\\build", "\\frontend-ts")

print("=== ① jixia-kernel 顶层 ===")
kd = os.path.join(REF, "jixia-kernel")
if os.path.isdir(kd):
    for d in sorted(os.listdir(kd))[:24]:
        p = os.path.join(kd, d)
        if os.path.isdir(p):
            print("   [dir] %s" % d)
        else:
            print("       %-34s %8d B" % (d, os.path.getsize(p)))

print()
print("=== ② 命中 /retrieve 等关键词的文件（按体积）===")
hits = []
for dp, dn, fn in os.walk(REF):
    if any(s in dp for s in SKIP):
        continue
    for f in fn:
        if not f.endswith((".py", ".rs", ".ts", ".js", ".sql", ".toml", ".json", ".md")):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if not re.search(r"retrieve|top_k|fts5|bm25|tantivy", t, re.I):
            continue
        rel = p.replace(REF + os.sep, "")
        hits.append((len(t), rel, t))
hits.sort(reverse=True)
for n, rel, _ in hits[:24]:
    print("   %8.1f KB  %s" % (n / 1024, rel[:100]))
print("   （共 %d 个）" % len(hits))

print()
print("=== ③ 逐个看命中处（每个文件最多 8 行）===")
for n, rel, t in hits[:8]:
    print("   ── %s" % rel[:100])
    ls = t.split("\n")
    cnt = 0
    for i, l in enumerate(ls, 1):
        if re.search(r"retrieve|top_k|fts5|bm25|tantivy|def .*retriev|fn .*retriev", l, re.I):
            print("      %5d| %s" % (i, l.strip()[:112]))
            cnt += 1
            if cnt >= 8:
                break
    print()
