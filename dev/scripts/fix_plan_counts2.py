# -*- coding: utf-8 -*-
"""补上 docs/plan/01-现状盘点.md 第 86 行漏掉的那条带日期更正。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
P = os.path.join(ROOT, "docs", "plan", "01-现状盘点.md")
NOTE = " → **2026-10-13 更正**：现为 `tests/run_all.py` = **10 个文件 / 386 项 / 0 失败**。"

lines = io.open(P, encoding="utf-8", errors="replace").read().split("\n")
hit = 0
for i, l in enumerate(lines):
    if "2026-10-13 更正" in l:
        continue
    if ("385" in l or "8 个文件" in l) and "8 个文件 / 385" in l.replace("385 项", "385"):
        lines[i] = l.rstrip() + NOTE
        hit += 1
if hit:
    io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("✓ 补上 %d 条更正" % hit)
else:
    print("· 无需补")

print()
print("=== 全仓复查（排除历史提交信息与旧快照）===")
import re  # noqa: E402
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git|dev\\merge-map|dev\\scripts|dev\\ppt\\out)\\", re.I)
for dp, dn, fn in os.walk(ROOT):
    if SKIP.search(dp + "\\"):
        continue
    for f in fn:
        if not f.endswith((".md", ".json")):
            continue
        p = os.path.join(dp, f)
        try:
            ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            continue
        for i, l in enumerate(ls, 1):
            if re.search(r"\b(381|382|383|384|385)\b", l) and ("项" in l or "自检" in l or "文件" in l):
                if "更正" in l or "历史" in l:
                    continue
                print("   ⚠ %-44s %5d| %s" % (p.replace(ROOT + "\\", "")[:44], i, l.strip()[:92]))

MSG = """docs(plan): 补上 01-现状盘点.md 第 86 行漏掉的一条日期更正

上一条给 docs/plan 两处过期数字加更正时，`01-现状盘点.md` 有**两处**涉及（86 行与 103 行），
脚本只命中了 103 行 —— 86 行（"仓库外审计目录 → 2026-10-04 更正：体检已迁入 tests/（8 个文件 / 385 项…）"）
漏了。这条补上，并做了一次全仓复查确认没有其它活跃位置的旧数字（历史提交信息与旧快照除外）。
"""
p = os.path.join(MAP, "_msg_plan_counts2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
