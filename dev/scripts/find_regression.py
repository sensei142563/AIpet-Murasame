# -*- coding: utf-8 -*-
"""定位并修回合并不小心覆盖掉的那处（focusInEvent 的 stop_voice=True）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=600):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


print("=== ① 找 focusInEvent / stop_voice 在哪 ===")
for f in sh(["git", "grep", "-l", "-n", "-E", "focusInEvent|stop_voice", "--",
             "*.py"]).split("\n"):
    if f.strip():
        print("   " + f.strip()[:110])

print()
print("=== ② 三方对比（只在含 focusInEvent 的文件里看这段）===")
TARGETS = [x for x in sh(["git", "grep", "-l", "-E", "focusInEvent", "--", "*.py"]).split("\n")
           if x.strip()]
for f in TARGETS:
    print("   ── %s" % f)
    for ref, tag in (("preMain-20261014", "合并前(我们)"), ("origin/main", "他们"),
                     ("HEAD", "合并后(现在)")):
        t = sh(["git", "show", "%s:%s" % (ref, f)])
        ls = t.split("\n")
        idx = [i for i, l in enumerate(ls) if "focusInEvent" in l]
        if not idx:
            print("      %-14s （没有 focusInEvent）" % tag)
            continue
        i = idx[0]
        seg = ls[i:i + 12]
        print("      %-14s：" % tag)
        for l in seg[:10]:
            print("         | " + l.rstrip()[:104])

print()
print("=== ③ 逐行找出差异（我们 vs 现在）===")
for f in TARGETS:
    a = sh(["git", "show", "preMain-20261014:%s" % f]).split("\n")
    b = sh(["git", "show", "HEAD:%s" % f]).split("\n")
    ai = [i for i, l in enumerate(a) if "focusInEvent" in l]
    bi = [i for i, l in enumerate(b) if "focusInEvent" in l]
    if not ai or not bi:
        continue
    i, j = ai[0], bi[0]
    seg_a = [l.strip() for l in a[i:i + 14] if l.strip()]
    seg_b = [l.strip() for l in b[j:j + 14] if l.strip()]
    import difflib
    for line in difflib.unified_diff(seg_a, seg_b, "我们", "现在", lineterm="", n=1):
        print("      " + line[:110])
