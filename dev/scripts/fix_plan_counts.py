# -*- coding: utf-8 -*-
"""按文档自身的体例，给 docs/plan 两处过期数字追加**带日期的更正**（不改历史数字）。

体例来源：`01-现状盘点.md` 自己就在用 "→ **2026-10-04 更正**：…" 的写法。
现状：两处都写 "8 个文件 / 385 项"；实为 "10 个文件 / 386 项"。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
NOTE = " → **2026-10-13 更正**：现为 `tests/run_all.py` = **10 个文件 / 386 项 / 0 失败**（本轮为 vision 接口与 TTS 记录加了回归守卫）。"
done = []

for rel, needles in (
    ("docs/plan/00-总体规划.md", ["= 8 个文件 / 385 项 通过"]),
    ("docs/plan/01-现状盘点.md",
     ["8 个文件 / 385 项 / 0 失败", "8 个体检文件 + `run_all.py` + `README.md`"]),
):
    p = os.path.join(ROOT, rel)
    lines = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    hit = 0
    for i, l in enumerate(lines):
        if "2026-10-13 更正" in l:
            continue
        if any(n in l for n in needles) and ("385" in l or "8 个" in l):
            lines[i] = l.rstrip() + NOTE
            hit += 1
    if hit:
        io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        done.append((rel, hit))
        print("✓ %s：追加 %d 条带日期更正" % (rel, hit))
    else:
        print("· %s：无需改（或已标注）" % rel)

print()
print("=== 复核 ===")
for rel, _ in done:
    for i, l in enumerate(io.open(os.path.join(ROOT, rel), encoding="utf-8",
                                 errors="replace").read().split("\n"), 1):
        if "2026-10-13 更正" in l:
            print("   %s %5d| …%s" % (rel, i, l.strip()[-96:]))

MSG = """docs(plan): 给两处过期自检数字追加带日期的更正（不改历史数字）

`docs/plan/00-总体规划.md` 与 `01-现状盘点.md` 里写着"8 个文件 / 385 项"，
而实测已是 **10 个文件 / 386 项 / 0 失败**。

处理方式：**不改历史数字**，按这两份文档**自己就在用的体例**
（它们已有 "→ **2026-10-04 更正**：…" 的写法）追加：
    → **2026-10-13 更正**：现为 `tests/run_all.py` = 10 个文件 / 386 项 / 0 失败
      （本轮为 vision 接口与 TTS 记录加了回归守卫）。

为什么不直接改数字：这两份是**带日期的盘点/规划快照**，当时的 8/385 是真实的；
抹掉它反而看不出"什么时候变成了 10/386"，而留下"何时更正"更有用。
（上一轮 README/PPT 那种**在用说明**才直接改数字 —— 两类文档两种处理。）
"""
p = os.path.join(MAP, "_msg_plan_counts.txt")
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
