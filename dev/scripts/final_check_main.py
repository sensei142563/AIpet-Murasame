# -*- coding: utf-8 -*-
"""收尾核对（只读）：
  ① 这次合并从他们那边实际拿进来了什么（相对合并前的我们）
  ② 我们的新增是否完好（README / 关键文件）
  ③ 本地与远端状态、工作区是否干净、自检是否绿
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=1200):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip()


print("=== ① 合并带进来的改动（相对合并前的我们 04ac40c）===")
out = sh(["git", "diff", "--stat", "preMain-20261014", "HEAD"])
lines = [l for l in out.split("\n") if l.strip()]
print("   " + (lines[-1] if lines else "（无差异）")[:140])
print("   文件清单（前 24 个）：")
ns = sh(["git", "diff", "--name-status", "preMain-20261014", "HEAD"])
for l in ns.split("\n")[:24]:
    if l.strip():
        print("      " + l.replace("\t", "  ")[:110])

print()
print("=== ② 我方关键内容是否完好 ===")
for ref, tag in (("04ac40c", "合并前(我们)"), ("HEAD", "合并后(现在)")):
    r = sh(["git", "show", "%s:README.md" % ref])
    print("   %-14s README %d 行" % (tag, len(r.split("\n"))))
o = sh(["git", "ls-files", "docs/plan"])
print("   docs/plan 下的文件（我们的规划文档）：%d 个" % len([x for x in o.split("\n") if x.strip()]))
for x in o.split("\n")[:6]:
    if x.strip():
        print("      " + x[:100])

print()
print("=== ③ 状态 ===")
print("   本地分支 = %s" % sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]))
print("   HEAD     = %s" % sh(["git", "log", "-1", "--format=%h %s"])[:100])
st = [l for l in sh(["git", "status", "--porcelain"]).split("\n")
      if l.strip() and not l.startswith("??")]
print("   已跟踪脏项 = %d %s" % (len(st), "✓ 干净" if not st else "✗"))
print("   本地 vs origin/main：%s（左=他们独有 右=我们独有）"
      % sh(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"]))
print("   本地 vs origin/readme-on-their-main：%s"
      % sh(["git", "rev-list", "--left-right", "--count",
            "origin/readme-on-their-main...HEAD"]))
print()
print("   远端分支：")
for l in sh(["git", "ls-remote", "--heads", "origin"]).split("\n"):
    if "refs/heads/" in l:
        h, n = l.split("\t")
        print("      %s  %s" % (h[:12], n.replace("refs/heads/", "")))

print()
print("=== ④ 安全网还在吗 ===")
for tag in ("preMain-20261014", "preB-20261014"):
    print("   tag %-22s → %s" % (tag, sh(["git", "rev-list", "-n", "1", tag])[:12]))
print("   refs/original：%s" % (sh(["git", "for-each-ref", "--format=%(refname)",
                                    "refs/original"])[:120] or "（无）"))
