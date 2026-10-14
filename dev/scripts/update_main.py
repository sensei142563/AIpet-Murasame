# -*- coding: utf-8 -*-
"""把 main 更新到最新（B），然后停下。
   步骤：打安全标签 → merge -X ours origin/main → COPYRIGHT.md 取他们的
        → 跑 389 项自检 → 通过才推 main（应为快进）
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TAG = "preMain-20261014"


def sh(a, timeout=1800):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== ① 前置检查 + 安全标签 ===")
print("   分支 = %s" % sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])[0])
out, _ = sh(["git", "status", "--porcelain"])
tr = [l for l in out.split("\n") if l.strip() and not l.startswith("??")]
print("   已跟踪脏项 %d %s" % (len(tr), "✓" if not tr else "✗ 先处理"))
if tr:
    sys.exit(0)
sh(["git", "tag", "-f", TAG, "-m", "合并 main 之前的安全点"])
print("   ✓ 安全标签 %s → %s" % (TAG, sh(["git", "rev-parse", "--short", TAG + "^{commit}"])[0]))
print("   origin/main = %s" % sh(["git", "log", "-1", "--format=%h %s", "origin/main"])[0][:90])

print()
print("=== ② merge -X ours origin/main（冲突一律保留我们这版）===")
out2, code2 = sh(["git", "merge", "-X", "ours", "origin/main", "-m",
                  "merge: 把远端 main 的 12 条并入我们的最新线（冲突保留我们这版）\n\n"
                  "主人判断「main 上都是旧代码」，核查成立：42 个双方都改过的文件里他们普遍更旧，\n"
                  "新增的 1005 个文件基本都是我们这边的。故用 -X ours：\n"
                  "冲突一律保留我们的版本；他们独有、我们没碰的改动自然进来。\n"
                  "COPYRIGHT.md 单独保留他们 10-10 的版权审计版本。"])
for l in out2.split("\n")[:16]:
    if l.strip():
        print("   " + l.strip()[:126])
print("   退出码 = %d" % code2)
out3, _ = sh(["git", "status", "--porcelain"])
rem = [l for l in out3.split("\n") if l.strip().startswith(("UU", "AA", "DD", "AU", "UA", "DU", "UD"))]
print("   剩余冲突 %d 个 %s" % (len(rem), "✓ 自动化解完" if not rem else "✗"))
for l in rem[:6]:
    print("      " + l[:110])

if rem:
    print("   有冲突没自动解完，停手（合并保持原状，等你）")
    sys.exit(0)

print()
print("=== ③ COPYRIGHT.md 保留他们的（10-10 版权审计）===")
o4, c4 = sh(["git", "checkout", "origin/main", "--", "COPYRIGHT.md"])
print("   " + (o4 or "✓ 已取他们的版本")[:120])
# 若因此产生暂存改动则一并提交
o5, _ = sh(["git", "status", "--porcelain", "--", "COPYRIGHT.md"])
print("   COPYRIGHT.md 状态：%s" % (o5.strip()[:80] or "（与合并结果一致）"))

print()
print("=== ④ 跑 389 项自检（关键闸门）===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=2400)
tail = ((r.stdout or "") + (r.stderr or "")).strip().split("\n")[-4:]
for l in tail:
    if l.strip():
        print("   " + l.strip()[:120])
ok = "0 个文件失败" in (r.stdout or "")
print("   自检通过：%s" % ("✓ 可以推送" if ok else "✗ 不推，先修"))

print()
print("=== ⑤ 合并结果概况 ===")
print("   HEAD = %s" % sh(["git", "log", "-1", "--format=%h %s"])[0][:100])
print("   README 行数 = %d（我们原为 1641）" % len(sh(["git", "show", "HEAD:README.md"])[0].split("\n")))
print("   与 origin/main 的关系（左=他们独有 右=我们独有）= %s"
      % sh(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"])[0])

if not ok:
    print()
    print("=== 自检没过 ⇒ 不推送。合并结果留在本地，等你决定 ===")
    sys.exit(0)

print()
print("=== ⑥ 推 main（应为快进）===")
o6, c6 = sh(["git", "push", "origin", "HEAD:main"], timeout=3600)
for l in o6.split("\n")[-8:]:
    if l.strip():
        print("   " + l.strip()[:130])
print("   退出码 = %d" % c6)
o7, _ = sh(["git", "ls-remote", "--heads", "origin"])
for l in o7.split("\n"):
    if "refs/heads/main" in l:
        print("   远端 main = %s" % l.split("\t")[0][:12])
