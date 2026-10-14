# -*- coding: utf-8 -*-
"""回答两个具体问题：
  ① 远端 main 上"我们没有的 12 条"到底是谁的、什么时候的（是不是 fish 新提交）
  ② 为什么以前能推 main、现在不能 —— 两条线是什么时候分开的
"""
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return (r.stdout or "") + (r.stderr or "")


print("=== ① 远端 main 独有、我们本地没有的提交（逐条带作者与日期）===")
out = sh(["git", "log", "--no-decorate", "--format=%h|%ad|%an|%s", "--date=short",
          "origin/main", "^HEAD"])
for l in out.split("\n"):
    if l.strip():
        p = l.split("|", 3)
        if len(p) == 4:
            print("   %s  %s  %-12s  %s" % (p[0], p[1], p[2][:12], p[3][:74]))

print()
print("=== ② 我们独有、远端 main 没有的提交（只看最近 12 条 + 最早 6 条）===")
out2 = sh(["git", "log", "--no-decorate", "--format=%h|%ad|%an|%s", "--date=short",
           "HEAD", "^origin/main"])
lines = [l for l in out2.split("\n") if l.strip()]
print("   （共 %d 条）" % len(lines))
for l in lines[:12]:
    p = l.split("|", 3)
    if len(p) == 4:
        print("   %s  %s  %-12s  %s" % (p[0], p[1], p[2][:12], p[3][:74]))
print("   …")
for l in lines[-6:]:
    p = l.split("|", 3)
    if len(p) == 4:
        print("   %s  %s  %-12s  %s" % (p[0], p[1], p[2][:12], p[3][:74]))

print()
print("=== ③ 两条线是什么时候分开的（共同祖先）===")
mb = sh(["git", "merge-base", "HEAD", "origin/main"]).strip()
print("   共同祖先 = %s" % mb[:12])
print("   " + sh(["git", "log", "-1", "--format=%h %ad %an  %s", "--date=short", mb]).strip())
print()
print("   从共同祖先之后，远端 main 走了 %s 条，我们走了 %s 条"
      % (sh(["git", "rev-list", "--count", mb + "..origin/main"]).strip(),
         sh(["git", "rev-list", "--count", mb + "..HEAD"]).strip()))

print()
print("=== ④ README 在各条线上是什么样 ===")
for ref, tag in ((mb, "共同祖先"), ("origin/main", "远端 main"), ("HEAD", "本地 HEAD")):
    r = sh(["git", "show", "%s:README.md" % ref])
    n = len(r.split("\n"))
    has_v119 = "1.19" in r or "V1.19" in r
    has_v117 = "1.17" in r or "V1.17" in r
    print("   %-10s README %4d 行  含V1.17=%s  含V1.19=%s" % (tag, n, has_v117, has_v119))

print()
print("=== ⑤ PR #7 那条合并的父提交（看它把哪条线并进了 main）===")
print(sh(["git", "log", "-1", "--format=%h %ad %an%n   %s%n   parents=%p", "--date=short",
          "b2d2419"]).strip())
