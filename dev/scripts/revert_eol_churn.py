# -*- coding: utf-8 -*-
"""紧急回退：把被我改成 CRLF 的文件退回 LF。
   安全闸：先确认所有待回退文件的 diff 都是"增删行数相等"（= 纯行尾改动），
          确认后才 git checkout；新写的未跟踪脚本不受影响。
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


print("=== ① 确认仓库的真实约定 ===")
print("   core.autocrlf =", sh(["git", "config", "--get", "core.autocrlf"]).strip() or "(未设)")
ga = os.path.join(ROOT, ".gitattributes")
if os.path.isfile(ga):
    print("   .gitattributes:")
    for l in open(ga, encoding="utf-8", errors="replace").read().split("\n")[:8]:
        print("      " + l[:100])
else:
    print("   .gitattributes: 不存在")
# 索引里某个文件的真实行尾
blob = subprocess.run(["git", "-C", ROOT, "show", "HEAD:README.md"], capture_output=True).stdout
print("   HEAD:README.md  索引里 CRLF=%d LF=%d  ⇒ 仓库约定是 %s"
      % (blob.count(b"\r\n"), blob.count(b"\n") - blob.count(b"\r\n"),
         "CRLF" if blob.count(b"\r\n") else "LF"))

print()
print("=== ② 安全闸：所有改动是否都是纯行尾 ===")
ns = [l for l in sh(["git", "diff", "--numstat"]).split("\n") if l.strip()]
bad = []
for l in ns:
    parts = l.split("\t")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        if parts[0] != parts[1]:
            bad.append(l)
    else:
        bad.append(l)
print("   改动文件 %d 个；其中增删不等（可能有真实内容改动）的：%d 个" % (len(ns), len(bad)))
for l in bad[:10]:
    print("      ⚠ " + l[:104])
if bad:
    print()
    print("   ⇒ 存在非行尾改动，**不自动回退**，等你确认。")
    sys.exit(0)
print("   ⇒ 全部是纯行尾改动 ✓ 可以安全回退")

print()
print("=== ③ 回退（tracked 文件恢复为 HEAD 原样；未跟踪的新脚本不受影响）===")
print(sh(["git", "checkout", "--", "."])[:200] or "   （无输出=成功）")
st = [l for l in sh(["git", "status", "--porcelain"]).split("\n") if l.strip()]
print("   回退后 status：%d 项" % len(st))
for l in st[:16]:
    print("      " + l[:110])

print()
print("=== ④ 复查行尾（应恢复为 LF）===")
for rel in ("README.md", "run.py", "pcl_launcher/silicon_window.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    d = open(p, "rb").read()
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    print("   %-38s CRLF=%-5d LF=%-6d %s" % (rel, crlf, lf,
                                             "✓ LF（与仓库一致）" if crlf == 0 else "⚠ 仍含 CRLF"))
