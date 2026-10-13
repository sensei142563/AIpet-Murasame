# -*- coding: utf-8 -*-
"""查 plugins 模块的调用点：我们树里怎么用的、备份里怎么用的，判断能否安全整file恢复。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dist\\",
        "\\build\\", "\\_internal\\", "\\GPT-SoVITS\\")


def show(ref, path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


def scan(text, label):
    print("=== %s ===" % label)
    hits = {}
    for i, l in enumerate(text.split("\n"), 1):
        if re.search(r"\bplugins\b|_plg|plg2", l) and re.search(r"\.\w+\(|\bimport\b", l):
            m = re.findall(r"(?:_plg\d*|plugins)\.([A-Za-z_][A-Za-z0-9_]*)", l)
            for name in m:
                hits.setdefault(name, []).append(i)
    for name in sorted(hits):
        print("   %-18s 被调用 %d 次，行 %s" % (name, len(hits[name]), hits[name][:6]))
    return hits


# 当前树的调用点（扫源码）
cur_calls = {}
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in SKIP):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        for i, l in enumerate(t.split("\n"), 1):
            for m in re.finditer(r"(?:_plg\d*|plugins)\.([A-Za-z_][A-Za-z0-9_]*)", l):
                cur_calls.setdefault(m.group(1), []).append("%s:%d" % (f, i))
print("=== 当前树：plugins 模块被调用的成员 ===")
for k in sorted(cur_calls):
    print("   %-18s %d 次  %s" % (k, len(cur_calls[k]), cur_calls[k][:4]))

print()
print("=== 当前树 tool/plugins.py 里定义了哪些成员 ===")
cur = io.open(os.path.join(ROOT, "tool", "plugins.py"), encoding="utf-8", errors="replace").read()
cur_defs = set(re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", cur, re.M))
print("   " + ", ".join(sorted(cur_defs)))

print()
print("=== 备份 tool/plugins.py 里定义了哪些成员 ===")
bak = show(REF_BAK, "tool/plugins.py")
bak_defs = set(re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", bak, re.M))
print("   " + ", ".join(sorted(bak_defs)))

print()
print("=== 关键：当前树调用点里，备份**没有**的成员（这些是短版接口，恢复后要改）===")
gap = [k for k in cur_calls if k not in bak_defs]
print("   " + (", ".join(sorted(gap)) or "（无）"))
print("=== 反之：备份有、当前调用点没用到但可能有用的成员（抽样）===")
extra = [k for k in bak_defs if k not in cur_defs]
print("   " + ", ".join(sorted(extra)))
