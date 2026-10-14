# -*- coding: utf-8 -*-
"""修正：上一条提交的信息里我引用了原话（反而把关键词写进了历史）—— 立即改成中性表述，
   并删掉含关键词的一次性脚本。然后复查工作区。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
KW = "\u5e08\u5144"

# ① 删掉带关键词的一次性脚本
for rel in ("dev/scripts/finish_privacy_cleanup.py",):
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if os.path.isfile(p):
        os.remove(p)
        print("✓ 删除 %s" % rel)

# ② 把提交信息稿改成中性表述（不再引用原话）
MSG = """chore(privacy): 文档/代码里去掉外部装置的个人指向（主人要求）

## 主人要求
有关外部装置的工作**尚未发表**，不得出现在本项目的文档或代码里。

## 做了什么（只去个人指向，技术结论保留）
```
dev/docs/安卓阶段决策-2026-10-13.md    "…那套装置（帕金森相关）" → "课题组另有一套动作识别装置（面向临床动作分析）"
docs/大厂入局与对标补查-2026-10-13.md   → "外部装置" / "需确认后才能写进方案"
dev/merge-map/_msg_mmwave.txt         同上
dev/scripts/commit_mmwave.py          同上
另删除了三个一次性排查脚本（其关键词表本身也会构成命中）。
```

## 落实情况
- 工作区**已无**该类指向（全仓扫描 0 处）；
- **PPT 本来就是干净的**：第 20 页只写"课题装置输出标准化参数流"，
  引用均为公开文献（mmHRI / 文心守护）；全篇无个人指向、无未发表细节；
- ⚠ **git 历史**：此前 3 个提交（如 `c81f8c7` / `6330779` / `111cf76`）的信息或内容里仍可能带有该类指向。
  清除需要改写历史（`git filter-repo` / 交互式 rebase），**属有风险操作，未擅自执行**，已报告主人由其决定。

## 验证
全仓扫描（排除 .git 与三方目录）0 处命中；提交后工作区干净。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_privacy.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
print("✓ 提交信息稿已改为中性表述")

# ③ amend 最后一条提交（未推送，安全）
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", ROOT, "commit", "--amend", "-F", p], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print("✓ amend：", (r.stdout or r.stderr or "").splitlines()[0][:140])

# ④ 复查
print()
print("=== 工作区复查 ===")
n = 0
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp for s in (".git", "runtime", "GPT-SoVITS", "F5-TTS_Models", "\\models",
                             "dev\\tmp", ".venv", "__pycache__", "NapCat", "_internal",
                             "three-demo", "tts_model_cache")):
        continue
    for f in fn:
        if not f.endswith((".py", ".md", ".json", ".txt")):
            continue
        fp = os.path.join(dp, f)
        try:
            t = io.open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if KW in t:
            print("   ⚠ %s" % os.path.relpath(fp, ROOT))
            n += 1
print("   命中 %d 处 %s" % (n, "✓ 干净" if n == 0 else "✗"))

print()
print("=== 最新提交 ===")
r2 = subprocess.run(["git", "-C", ROOT, "log", "--oneline", "-2"], capture_output=True,
                    text=True, encoding="utf-8", errors="replace")
for l in (r2.stdout or "").split("\n"):
    if l.strip():
        print("   " + l[:120])
st = [l for l in subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace").stdout.split("\n") if l.strip()]
print("   工作区 %s" % ("干净 ✓" if not st else "%d 项" % len(st)))
