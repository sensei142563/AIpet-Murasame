# -*- coding: utf-8 -*-
"""① 确认行尾批量转换对 git 的影响（core.autocrlf=true 下应无 diff）
   ② 盘点三个克隆仓库里与"记忆/检索/情绪"相关的实现文件
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF = r"E:\university\order\research-refs"


def sh(args, cwd=ROOT):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "") + (r.stderr or "")


print("=== ① git 怎么看这次行尾批量转换 ===")
print("   autocrlf =", sh(["git", "config", "--get", "core.autocrlf"]).strip())
st = [l for l in sh(["git", "status", "--porcelain"]).split("\n") if l.strip()]
print("   status 改动 %d 项" % len(st))
for l in st[:14]:
    print("      " + l[:108])
ns = [l for l in sh(["git", "diff", "--numstat"]).split("\n") if l.strip()]
print("   diff --numstat %d 个文件" % len(ns))
for l in ns[:14]:
    print("      " + l[:108])
if not ns:
    print("   ⇒ **没有任何内容 diff** ✓ 说明 git 已归一化，行尾转换无害 ✓")

print()
print("=== ② 三个克隆仓库：记忆/检索/情绪 相关文件 ===")
PAT = re.compile(r"memory|retriev|search|recall|embed|vector|bm25|fts|graph|"
                 r"mood|emotion|affection|relationship|sentiment|persona", re.I)
SKIP = ("\\.git", "node_modules", "__pycache__", "\\.venv", "target", "dist", "build",
        "tests/", "test_", "\\.png", "\\.jpg")
for repo in sorted(os.listdir(REF)):
    rd = os.path.join(REF, repo)
    if not os.path.isdir(rd):
        continue
    print("   ── %s ──" % repo)
    # README 行数
    for nm in ("README.md", "readme.md"):
        p = os.path.join(rd, nm)
        if os.path.isfile(p):
            n = len(io.open(p, encoding="utf-8", errors="replace").read().split("\n"))
            print("      README.md %d 行" % n)
    hits = []
    for dp, dn, fn in os.walk(rd):
        if any(s in dp for s in SKIP):
            continue
        for f in fn:
            if not f.endswith((".py", ".ts", ".md", ".go", ".rs")):
                continue
            rel = os.path.join(dp, f).replace(rd + os.sep, "")
            if PAT.search(rel):
                try:
                    sz = os.path.getsize(os.path.join(dp, f))
                except OSError:
                    continue
                hits.append((sz, rel))
    hits.sort(reverse=True)
    for sz, rel in hits[:10]:
        print("      %8.1f KB  %s" % (sz / 1024, rel[:96]))
    print("      （共 %d 个相关文件）" % len(hits))
