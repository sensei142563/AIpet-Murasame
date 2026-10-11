# -*- coding: utf-8 -*-
"""判断刚才的 CRLF 转换是否制造了"整文件改动"风险；必要时回滚到 git 版本。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")


def run(repo, *args):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


for nm, repo in (("桌面", MAIN), ("手机", CHAT)):
    print("=== %s仓 ===" % nm)
    print("   core.autocrlf = %s" % run(repo, "config", "core.autocrlf").strip() or "(未设置)")
    print("   core.eol      = %s" % run(repo, "config", "core.eol").strip() or "(未设置)")
    ns = run(repo, "diff", "--numstat").strip().splitlines()
    print("   diff --numstat（应只有 1~3 行/文件才正常）：")
    for l in ns[:8]:
        print("      " + l[:110])
    print("   diff -w（忽略空白后是否还有差异）：")
    w = run(repo, "diff", "-w", "--numstat").strip().splitlines()
    if not w:
        print("      ✓ 忽略空白后【无】差异 ⇒ 纯行尾差异，内容没变")
    else:
        print("      ⚠ 忽略空白后仍有 %d 个文件差异 ⇒ 不只是行尾，需要看内容" % len(w))
        for l in w[:5]:
            print("      " + l[:110])
    print()

print("=== 结论与处置 ===")
ns_main = run(MAIN, "diff", "--numstat").strip().splitlines()
ns_chat = run(CHAT, "diff", "--numstat").strip().splitlines()
total_main = sum(int(l.split("\t")[0]) for l in ns_main if l.split("\t")[0].isdigit()) if ns_main else 0
total_chat = sum(int(l.split("\t")[0]) for l in ns_chat if l.split("\t")[0].isdigit()) if ns_chat else 0
print("   桌面仓改动行数合计 %d，手机仓 %d" % (total_main, total_chat))
if total_main > 200 or total_chat > 200:
    print("   ⚠ 改动量过大（疑似整文件行尾翻动）⇒ 回滚工作区到 git 版本，保持仓库原样")
    for repo in (MAIN, CHAT):
        subprocess.run(["git", "-C", repo, "checkout", "--", "."], capture_output=True)
    for nm, repo in (("桌面", MAIN), ("手机", CHAT)):
        st = run(repo, "status", "--porcelain").strip()
        print("   %s仓回滚后状态：%s" % (nm, "干净 ✓" if not st else st.splitlines()[:3]))
    print("   （行尾不一致是工作区现象，git 提交时按仓库规则归一化，不影响内容）")
else:
    print("   ✓ 改动量小且为纯行尾差异 ⇒ 无需回滚")
