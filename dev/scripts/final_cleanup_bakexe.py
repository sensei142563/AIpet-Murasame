# -*- coding: utf-8 -*-
"""收尾：把合并带回来的备份 exe 再摘掉（文件留在硬盘）→ 提交 → 推 main → 停。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=2400):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== ① 摘掉被带回来的备份 exe ===")
o, c = sh(["git", "rm", "--cached", "--quiet", "--", "AIpet-Murasame.exe.bak_1604"])
print("   " + (o or "✓ 已从 git 摘掉（硬盘文件保留）")[:110])
fp = os.path.join(ROOT, "AIpet-Murasame.exe.bak_1604")
print("   硬盘上仍在：%s" % ("✓" if os.path.isfile(fp) else "✗"))
gi = os.path.join(ROOT, ".gitignore")
t = io.open(gi, encoding="utf-8", errors="replace").read()
if "*.exe.bak_*" in t:
    print("   .gitignore 已有 *.exe.bak_* 规则 ✓（合并后会被忽略）")
else:
    io.open(gi, "w", encoding="utf-8", newline="\n").write(t + "\n*.exe.bak_*\n")
    print("   ✓ 已补 .gitignore")

MSG = """chore(repo): 摘掉合并时被带回来的备份 exe（AIpet-Murasame.exe.bak_1604）

远端 main 上仍有这个 3.8MB 的旧备份 exe，`git merge` 时被带回我们的树里。
它已被 .gitignore 的 `*.exe.bak_*` 覆盖，本次再从 git 摘掉（**硬盘文件保留**）。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_bakexe.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
sh(["git", "add", "-A"])
o2, c2 = sh(["git", "commit", "-F", p])
print("   " + ((o2.splitlines()[0] if o2 else "")[:130]))

print()
print("=== ② 自检 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=2400)
out = (r.stdout or "") + (r.stderr or "")
for l in out.strip().split("\n")[-3:]:
    if l.strip():
        print("   " + l.strip()[:120])
ok = "0 个文件失败" in out

print()
print("=== ③ 推 main（若自检绿）===")
if ok:
    o3, c3 = sh(["git", "push", "origin", "HEAD:main"], timeout=3600)
    for l in o3.split("\n")[-6:]:
        if l.strip():
            print("   " + l.strip()[:130])
    print("   退出码 = %d" % c3)
else:
    print("   自检未过 ⇒ 不推")

print()
print("=== ④ 最终状态 ===")
print("   HEAD = %s" % sh(["git", "log", "-1", "--format=%h %s"])[0][:100])
print("   本地 vs origin/main = %s" % sh(["git", "rev-list", "--left-right", "--count",
                                          "origin/main...HEAD"])[0])
st = [l for l in sh(["git", "status", "--porcelain"])[0].split("\n")
      if l.strip() and not l.startswith("??")]
print("   已跟踪脏项 = %d %s" % (len(st), "✓ 干净" if not st else "✗"))
print("   远端：")
for l in sh(["git", "ls-remote", "--heads", "origin"])[0].split("\n"):
    if "refs/heads/" in l:
        h, n = l.split("\t")
        print("      %s  %s" % (h[:12], n.replace("refs/heads/", "")))
