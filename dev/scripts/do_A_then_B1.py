# -*- coding: utf-8 -*-
"""A：推送到同名新分支（不动 main）
   B 第一步：打安全标签 → 开始合并 origin/main → 统计 9 个冲突文件各自的差异规模
"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TAG = "preB-20261014"


def sh(args, timeout=900):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


print("=== A：推送到 origin/readme-on-their-main（不动 main）===")
out, code = sh(["git", "push", "origin", "readme-on-their-main:readme-on-their-main"])
for l in out.split("\n")[-6:]:
    if l.strip():
        print("   " + l.strip()[:130])
print("   退出码 = %d" % code)
out2, _ = sh(["git", "ls-remote", "--heads", "origin"])
pushed = "readme-on-their-main" in out2
print("   远端是否已有该分支：%s" % ("✓ 有（A 成功）" if pushed else "✗ 没有"))
if pushed:
    for l in out2.split("\n"):
        if "readme-on-their-main" in l:
            print("      " + l.strip())
    print("   ⇒ 在线地址：https://github.com/sensei142563/AIpet-Murasame/tree/readme-on-their-main")

print()
print("=== B-1：给当前状态打安全标签（随时可回到这里）===")
tagout, _ = sh(["git", "tag", "-f", TAG, "-m", "合并远端 main 之前的安全点（175 条工作线）"])
print("   " + (tagout or "✓ 已打标签 %s" % TAG)[:120])
cur, _ = sh(["git", "rev-parse", "--short", TAG])
print("   标签指向 %s" % cur)

print()
print("=== B-2：开始合并 origin/main ===")
out3, code3 = sh(["git", "merge", "origin/main"])
for l in out3.split("\n")[:16]:
    if l.strip():
        print("   " + l.strip()[:126])
print("   退出码 = %d" % code3)

print()
print("=== B-3：冲突文件与差异规模 ===")
st, _ = sh(["git", "status", "--porcelain"])
conf = [l[3:].strip().strip('"') for l in st.split("\n")
        if l.strip().startswith(("UU", "AA", "DD", "AU", "UA", "DU", "UD"))]
print("   冲突文件 %d 个：" % len(conf))
for f in conf:
    # 我们与他们各自的版本行数、以及相对共同祖先的改动量
    ours, _ = sh(["git", "show", "HEAD:" + f])
    theirs, _ = sh(["git", "show", "origin/main:" + f])
    base, _ = sh(["git", "show", "332848f:" + f])
    n_conf, _ = sh(["git", "diff", "--check", "--", f])
    markers, _ = sh(["git", "grep", "-c", "-E", r"^(<<<<<<<|=======|>>>>>>>)", "--", f])
    print("   ── %s" % f)
    print("        行数：共同祖先 %4d ｜ 我们 %4d ｜ 远端 %4d"
          % (base.count("\n"), ours.count("\n"), theirs.count("\n")))
    # 冲突标记数量
    import io
    p = ROOT + "\\" + f.replace("/", "\\")
    try:
        t = io.open(p, encoding="utf-8", errors="replace").read()
        n_ours = t.count("<<<<<<<")
        print("        冲突段数：%d" % n_ours)
    except Exception as e:
        print("        （读不了：%s）" % e)
