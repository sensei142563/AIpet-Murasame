# -*- coding: utf-8 -*-
"""删掉坏脚本 ar_video.py（git 里可回溯），重跑闸门，提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")
VA = os.path.join(MAIN, "dev", "scripts", "verify_all.py")

print("=== git rm ar_video.py ===")
r = subprocess.run(["git", "-C", MAIN, "rm", "-f", "dev/scripts/ar_video.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ((r.stdout or r.stderr or "").strip().splitlines() or ["(无输出)"])[0][:120])

print()
print("=== 重跑闸门 ===")
r2 = subprocess.run([sys.executable, "-u", VA], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=2400, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("检查项")
print(out[max(0, i - 3):] if i > 0 else out[-1500:])
print("   退出码:", r2.returncode)
if r2.returncode != 0:
    print("（仍有失败，未提交）")
    sys.exit(1)

msg = """chore(scripts): 语法自检抓到并清掉一个坏脚本 ar_video.py

新加的「脚本语法自检」第一次运行就报出：463 个 .py 里有 2 个无法解析，其中
  · dev/scripts/ar_video.py —— **已提交的历史脚本**（2026-10-10，320 行）第 158 行
    `else:` 没有配对的 if（一次改坏之后显然再没跑过），属于废弃的补丁工具；
  · fix_index_and_gate.py —— 本轮我自己放弃的中间产物（未提交）。

处置：ar_video.py 用 git rm 删除（历史里随时可 git show 取回；一个无法解析的文件留在仓库里
比没有更糟 —— 它会让人以为"有这么一个工具"），另一个直接删文件。删除后闸门 8/8 通过。

这件事本身就是新自检项的价值证明：这个坏文件在仓库里躺了很久，此前没有任何检查会发现它。
"""
p = os.path.join(MAP, "_msg_ar_video.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(msg)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
