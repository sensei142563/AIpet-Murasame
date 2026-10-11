# -*- coding: utf-8 -*-
"""排掉"交接清单自身的提交"造成的自指条目，重新生成并提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
G = os.path.join(MAIN, "dev", "scripts", "make_handover.py")

t = io.open(G, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        h, subj, body = parts[0].strip(), parts[1].strip(), parts[2]'''
new = '''        h, subj, body = parts[0].strip(), parts[1].strip(), parts[2]
        # 排掉"交接清单自身"的提交：否则文档会把自己对未验证项的**描述**当成未验证项列出来（自指）
        if subj.startswith("docs(handover)") or subj.startswith("docs: 交接清单"):
            continue'''
if old in t and "自指" not in t:
    t = t.replace(old, new, 1)
    io.open(G, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已排掉自指条目")
else:
    print("· 已处理或无锚点")

print()
r = subprocess.run([sys.executable, "-u", G], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.search(r"已生成|未验证项检索", l):
        print("   " + l.strip()[:150])

DOC = os.path.join(MAIN, "dev", "docs", "交接清单-2026-10.md")
txt = io.open(DOC, encoding="utf-8").read()
i = txt.find("## 四、")
j = txt.find("另外这些")
print()
print("=== 第四节（清理后）===")
print(txt[i:j] if i > 0 and j > i else "(未找到)")
print("=== 自指检查 ===")
self_ref = "交接清单（从真实状态自动生成" in (txt[i:j] if i > 0 and j > i else "")
print("   仍含自指条目：%s" % ("是 ✗" if self_ref else "否 ✓"))
print("   文档共 %d 行" % len(txt.split(chr(10))))

print()
MSG = """docs(handover): 排掉交接清单自身的提交（自指条目）

上一版第四节里出现了"docs: 交接清单（从真实状态自动生成…）"这条 ——
那是文档对自己描述文本的自我引用，不是真的未验证项。
已跳过 subject 以 docs(handover)/docs: 交接清单 开头的提交。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_handover3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", r"E:\university\order\python\pet\chatter"), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
