# -*- coding: utf-8 -*-
"""把"分支/仓库"的来龙去脉查清楚，好用大白话解释：
  ① 推送到底有没有发生（远端分支列表）
  ② fish9269/AIpet-Murasame 还在不在（只读查询，不推送）
  ③ 本地这些分支都是什么时候、由谁建的（首次出现的提交与日期）
  ④ 远端 main 上那条协作者 PR 是什么
"""
import io
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, timeout=300):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


print("=== ① 推送有没有发生？（远端当前分支）===")
out, _ = sh(["git", "ls-remote", "--heads", "origin"])
for l in out.split("\n"):
    if l.strip():
        print("   " + l.strip())
if "readme-on-their-main" in out:
    print("   ⇒ 新分支**已经推上去了**")
else:
    print("   ⇒ 远端**没有** readme-on-their-main ⇒ **刚才那次推送被打断，没推上去** ✓")

print()
print("=== ② fish9269/AIpet-Murasame 还在不在（只读）===")
out2, code2 = sh(["git", "ls-remote", "--heads", "https://github.com/fish9269/AIpet-Murasame.git"],
                 timeout=180)
if code2 == 0 and out2.strip():
    print("   ✓ 仓库还在，分支：")
    for l in out2.split("\n")[:10]:
        if l.strip():
            print("      " + l.strip())
else:
    print("   ✗ 查不到（可能已删/改名/私有，或没网络权限）")
    print("      原始输出：%s" % (out2.strip()[:200] or "(空)"))

print()
print("=== ③ 本机这些分支的来历（各自最早的独有提交）===")
for br in ("main", "readme-on-their-main", "backup/collaborator-main-20260929",
           "local_dev_history", "local_pre_purge", "merge/from-theirs"):
    out3, _ = sh(["git", "log", "-1", "--format=%h %ad %s", "--date=short", br])
    print("   %-38s %s" % (br, out3.strip()[:96]))

print()
print("=== ④ 远端 main 上那条协作者 PR ===")
out4, _ = sh(["git", "log", "-1", "--format=%h %ad %an <%ae>%n   %s%n   %b",
              "--date=short", "b2d2419"])
print("   " + out4.strip()[:400].replace("\n", "\n   "))

print()
print("=== ⑤ 协作者相关痕迹（仓库里出现过的协作者名）===")
out5, _ = sh(["git", "log", "--all", "--format=%an|%ae", "-400"])
from collections import Counter
c = Counter(l.strip() for l in out5.split("\n") if l.strip())
for who, n in c.most_common(8):
    print("   %-52s %4d 次提交" % (who[:52], n))
