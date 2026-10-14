# -*- coding: utf-8 -*-
"""核实我们自己的现状（写调研报告要用）：
  ① 好感度/关系值：在哪、什么字段、有没有衰减、有没有上限
  ② 记忆：怎么存、怎么读、是不是"全量塞进提示词"（这就是"能不能像数据库查找"的出发点）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ① 好感度/关系值 相关代码 ===")
PAT1 = re.compile(r"affinity|favor|好感|关系值|relation|intimacy|mood|情绪", re.I)
for rel in ("tool/state.py", "qq/qq_galgame.py", "tool/chat.py", "tool/attention.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    hits = [(i, l) for i, l in enumerate(ls, 1) if PAT1.search(l)]
    print("   ── %s（%d 行命中 / 共 %d 行）" % (rel, len(hits), len(ls)))
    for i, l in hits[:14]:
        print("      %5d| %s" % (i, l.strip()[:104]))

print()
print("=== ② 记忆相关：存储与读取 ===")
for rel in ("qq/qq_memory.py", "tool/self_learn.py", "tool/status_snapshot.py",
            "tool/memory_transfer.py", "longtext/longtext_history.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print("   （缺 %s）" % rel)
        continue
    t = io.open(p, encoding="utf-8", errors="replace").read()
    ls = t.split("\n")
    print("   ── %s（%d 行）" % (rel, len(ls)))
    # 关键信号：读文件 / 写入提示词 / 检索 / 条数限制
    SIG = re.compile(r"json\.load|json\.dump|open\(|prompt|system|limit|\[-\d+:\]|"
                     r"recent|history|search|检索|embed|top_k|slice", re.I)
    n = 0
    for i, l in enumerate(ls, 1):
        if SIG.search(l) and l.strip() and not l.strip().startswith("#"):
            print("      %5d| %s" % (i, l.strip()[:100]))
            n += 1
            if n >= 12:
                break

print()
print("=== ③ 记忆文件实际长什么样（挑几个看结构）===")
pets = os.path.join(ROOT, "pets")
for d in sorted(os.listdir(pets))[:3]:
    md = os.path.join(pets, d, "memory")
    if not os.path.isdir(md):
        continue
    print("   ── pets/%s/memory/" % d)
    for f in sorted(os.listdir(md))[:8]:
        fp = os.path.join(md, f)
        sz = os.path.getsize(fp)
        head = ""
        try:
            head = io.open(fp, encoding="utf-8", errors="replace").read()[:150].replace("\n", " ")
        except Exception:
            head = "(读不了)"
        print("      %-26s %8d B  %s" % (f, sz, head[:88]))
