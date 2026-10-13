# -*- coding: utf-8 -*-
"""修 操作单第 33 行里第二个漏掉的旧数字（"自带 381 项自检"），然后全仓再扫一遍。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
P = os.path.join(ROOT, "dev", "docs", "PPT录屏截图操作单-2026-10-13.md")

t = io.open(P, encoding="utf-8", errors="replace").read()
old, new = "自带 381 项自检", "自带 386 项自检"
if old in t:
    t = t.replace(old, new)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已修：「%s」→「%s」" % (old, new))
else:
    print("· 未命中（可能已改）")

print()
print("=== 全仓复查（在建的活文档里找 381~385 + 项/自检）===")
SKIP = re.compile(r"\\(runtime|\.venv|site-packages|GPT-SoVITS|_import_tmp|\.git"
                  r"|dev\\merge-map|dev\\scripts|dev\\ppt\\out|docs\\handover)\\", re.I)
bad = 0
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
                if "更正" in l or "历史" in l or "原为" in l:
                    continue
                print("   ⚠ %-46s %5d| %s" % (p.replace(ROOT + "\\", "")[:46], i, l.strip()[:88]))
                bad += 1
print("   （无输出 = 活跃文档里已无旧数字 ✓）" if bad == 0 else "   共 %d 处待看" % bad)

MSG = """docs(ppt): 修录屏操作单里漏掉的第二个旧数字（自带 381 → 386）

上一条把操作单里 3 处旧数字改了，但第 33 行（S8 那一行）**有两个数字**：
    `总计 10 个文件 / 386 项通过 / 0 个文件失败`（已改）… **工程质量：自带 381 项自检，全绿**（漏了）
本轮自查时用一个"扫 381~385 + 项/自检"的脚本全仓复查，把它抓了出来并修掉。
⇒ 结论：改数字不能只按"我记住的那几处"来，**要用扫描脚本复查**（这条和今天几次教训同源）。
"""
p = os.path.join(MAP, "_msg_counts3.txt")
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
