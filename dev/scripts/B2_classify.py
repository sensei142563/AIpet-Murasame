# -*- coding: utf-8 -*-
"""把 35 个冲突分类，判断哪些是"一键可解"、哪些要真判断。
   （合并仍在进行中；本脚本只读，不改任何文件。）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=900):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


out, _ = sh(["git", "status", "--porcelain"])
rows = []
for l in out.split("\n"):
    if not l.strip():
        continue
    code = l[:2]
    if code in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
        p = l[3:].strip()
        if p.startswith('"') and p.endswith('"'):
            p = p[1:-1]
        rows.append((code, p))

KIND = {
    "UU": "两边都改了（要真判断）",
    "AA": "两边都新增（要真判断）",
    "DU": "我们删了 / 他们改了（多半按我们删）",
    "UD": "他们删了 / 我们改了（要看）",
    "AU": "我们新增 / 他们新增",
    "UA": "他们新增 / 我们新增",
    "DD": "两边都删（不该出现）",
}
print("=== 35 个冲突按类型分类 ===")
from collections import Counter
c = Counter(code for code, _ in rows)
for code, n in c.most_common():
    print("   %s  %2d 个   %s" % (code, n, KIND.get(code, "?")))

print()
print("=== 逐个：类型 + 冲突段数 + 我们/他们的行数 ===")
by_kind = {}
for code, f in sorted(rows, key=lambda x: (x[0], x[1])):
    fp = os.path.join(ROOT, f.replace("/", "\\"))
    nblk, ol_tot, tl_tot = 0, 0, 0
    try:
        t = io.open(fp, encoding="utf-8", errors="replace").read()
        blocks = re.findall(r"<<<<<<<[^\n]*\n(.*?)=======\n(.*?)>>>>>>>[^\n]*\n", t, re.S)
        nblk = len(blocks)
        for o, th in blocks:
            ol_tot += len([x for x in o.split("\n") if x.strip()])
            tl_tot += len([x for x in th.split("\n") if x.strip()])
    except Exception:
        nblk = -1
    by_kind.setdefault(code, []).append((f, nblk, ol_tot, tl_tot))

for code in sorted(by_kind):
    print()
    print("   ── %s（%s）" % (code, KIND.get(code, "?")))
    for f, nblk, ol, tl in by_kind[code]:
        print("      %-58s 段=%-3s 我们%-5s 他们%-5s" % (f[:58], nblk, ol, tl))

print()
print("=== 汇总判断 ===")
trivial = sum(len(v) for k, v in by_kind.items() if k in ("DU", "DD"))
real = sum(len(v) for k, v in by_kind.items() if k in ("UU", "AA", "UD", "AU", "UA"))
print("   可能一键按我们处理：%d 个" % trivial)
print("   需要真判断：%d 个" % real)
print()
print("   我们这一侧被删掉的文件数（这次摘掉的）：")
o, _ = sh(["git", "diff", "--name-only", "--diff-filter=D", "origin/main...HEAD"])
print("      %d 个" % len([x for x in o.split("\n") if x.strip()]))
