# -*- coding: utf-8 -*-
"""零风险预演：在临时分支上把 origin/main 合进来，看会冲突在哪、能不能自动合。
   全程不动 readme-on-their-main；结束后清理临时分支与合并状态。
"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TMP = "rehearsal/merge-main"


def sh(args, timeout=600):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


cur, _ = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
print("当前分支：%s" % cur)
dirty, _ = sh(["git", "status", "--porcelain"])
print("工作区：%s" % ("干净 ✓" if not dirty else "有改动 ✗（先别试）"))

print()
print("=== ① 建临时分支 ===")
print("   " + (sh(["git", "branch", "-D", TMP])[0] or "(无旧分支)")[:80])
print("   " + sh(["git", "checkout", "-b", TMP])[0][:120])

print()
print("=== ② 试合 origin/main（不提交）===")
out, code = sh(["git", "merge", "--no-commit", "--no-ff", "origin/main"])
for l in out.split("\n")[:14]:
    if l.strip():
        print("   " + l.strip()[:120])
print("   退出码 = %d" % code)

print()
print("=== ③ 冲突/改动清单 ===")
out2, _ = sh(["git", "status", "--porcelain"])
conf = [l for l in out2.split("\n") if l.strip().startswith(("UU", "AA", "DD", "AU", "UA", "DU", "UD"))]
other = [l for l in out2.split("\n") if l.strip() and l not in conf]
print("   ⚠ 冲突文件 %d 个：" % len(conf))
for l in conf[:20]:
    print("      " + l[:110])
print("   （无冲突的自动合并改动 %d 项）" % len(other))
for l in other[:10]:
    print("      " + l[:110])

if conf:
    print()
    print("   README 是否在冲突里：%s" % ("是 ✗" if any("README" in l for l in conf) else "否 ✓"))
    print("   我们这版 README 行数 = %s" % sh(["git", "show", "HEAD:README.md"])[0].count("\n"))
    print("   远端 main 那版行数   = %s" % sh(["git", "show", "origin/main:README.md"])[0].count("\n"))

print()
print("=== ④ 清理：放弃合并 + 回原分支 + 删临时分支 ===")
if code != 0 or conf:
    print("   " + (sh(["git", "merge", "--abort"])[0] or "(已放弃合并)")[:80])
print("   " + sh(["git", "checkout", cur])[0][:120])
print("   " + (sh(["git", "branch", "-D", TMP])[0] or "")[:120])
print()
now, _ = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])
d2, _ = sh(["git", "status", "--porcelain"])
print("   现在分支 = %s，工作区 %s" % (now, "干净 ✓" if not d2 else "有改动 ✗"))
