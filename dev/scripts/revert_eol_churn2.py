# -*- coding: utf-8 -*-
"""回退行尾改动：排除 dev/ppt/out/（那里是我刚重新生成的成品图），其余 tracked 文件恢复 HEAD。
   安全闸：文本文件必须"增删行数相等"（纯行尾）；二进制（numstat 显示 - -）直接放过。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "") + (r.stderr or "")


ns = [l for l in sh(["git", "diff", "--numstat"]).split("\n") if l.strip()]
bad = []
for l in ns:
    parts = l.split("\t")
    if len(parts) < 3:
        continue
    a, d, path = parts[0], parts[1], parts[2]
    if path.startswith("dev/ppt/out/"):
        continue                       # 成品图，保留
    if a == "-" or d == "-":
        continue                       # 二进制，放过
    if not (a.isdigit() and d.isdigit() and a == d):
        bad.append(l)

print("=== ① 安全闸（已排除 dev/ppt/out/、已放过二进制）===")
print("   待回退 %d 个文件；增删不等的：%d 个" % (len(ns), len(bad)))
for l in bad[:8]:
    print("      ⚠ " + l[:104])
if bad:
    print("   ⇒ 有真实内容改动，**不自动回退**")
    sys.exit(0)
print("   ⇒ 全是纯行尾 ✓ 开始回退")

print()
print("=== ② 回退（排除 dev/ppt/out/）===")
out = sh(["git", "checkout", "--", ".",
          ":(exclude)dev/ppt/out"])
print("   " + (out.strip()[:300] if out.strip() else "（无输出=成功）"))
st = [l for l in sh(["git", "status", "--porcelain"]).split("\n") if l.strip()]
print("   回退后 status：%d 项" % len(st))
for l in st[:20]:
    print("      " + l[:112])

print()
print("=== ③ 复查行尾（应恢复 LF）===")
for rel in ("README.md", "run.py", "pcl_launcher/silicon_window.py",
            "dev/docs/汇报PPT规划-2026-10-13.md"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    d = open(p, "rb").read()
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    print("   %-46s CRLF=%-5d LF=%-6d %s" % (rel[:46], crlf, lf,
                                             "✓ LF 与仓库一致" if crlf == 0 else "⚠ 仍有 CRLF"))
