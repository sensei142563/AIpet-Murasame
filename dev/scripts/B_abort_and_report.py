# -*- coding: utf-8 -*-
"""放弃这次合并，恢复干净状态；并给出 B 的几条可选路线（供主人定）。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=900):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== 放弃合并 ===")
o, _ = sh(["git", "merge", "--abort"])
print("   " + (o or "（已放弃）")[:100])
print("   当前分支 = %s" % sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])[0])
print("   HEAD = %s" % sh(["git", "log", "-1", "--format=%h %s"])[0][:100])
print("   合并残留 = %s" % ("有 ✗" if os.path.exists(os.path.join(ROOT, ".git", "MERGE_HEAD"))
                            else "无 ✓"))
out, _ = sh(["git", "status", "--porcelain"])
tr = [l for l in out.split("\n") if l.strip() and not l.startswith("??")]
print("   已跟踪脏项 %d 个 %s" % (len(tr), "✓ 干净" if not tr else "✗"))

print()
print("=== 远端现状（A 的成果）===")
o2, _ = sh(["git", "ls-remote", "--heads", "origin"])
for l in o2.split("\n"):
    if l.strip():
        print("   " + l.strip()[:110])
print("   ⇒ 我们的工作线已在远端 ✓ https://github.com/sensei142563/AIpet-Murasame/tree/readme-on-their-main")

print()
print("=== B 的规模（供决策）===")
o3, _ = sh(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"])
print("   远端 main 独有 / 我们独有 = %s" % o3)
o4, _ = sh(["git", "diff", "--shortstat", "origin/main", "HEAD"])
print("   两条线的文件差异：%s" % o4[:200])
o5, _ = sh(["git", "diff", "--name-status", "origin/main", "HEAD"])
mod = sum(1 for l in o5.split("\n") if l.startswith("M"))
add = sum(1 for l in o5.split("\n") if l.startswith("A"))
dele = sum(1 for l in o5.split("\n") if l.startswith("D"))
print("   修改 %d / 新增 %d / 删除 %d 个文件" % (mod, add, dele))
