# -*- coding: utf-8 -*-
"""只读检查：真实记忆里那 7 条"重复"是什么？记录里有没有 id/messageId 可用？"""
import io
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
p = os.path.join(MAIN, "pets", "murasame", "memory", "history.json")
d = json.loads(io.open(p, encoding="utf-8").read())
recs = d.get("history", []) if isinstance(d, dict) else d
print("共 %d 条" % len(recs))

print()
print("=== 记录里出现过的键（看有没有 id/messageId）===")
keys = Counter()
for e in recs:
    if isinstance(e, dict):
        for k in e.keys():
            keys[k] += 1
for k, n in keys.most_common():
    print("   %-16s 出现在 %d 条中" % (k, n))

print()
print("=== 时间戳样例与精度 ===")
for e in recs[:3]:
    print("   %s" % json.dumps(e, ensure_ascii=False)[:150])
ts = [str(e.get("timestamp", "")) for e in recs if isinstance(e, dict)]
print("   时间戳长度分布：%s" % Counter(len(x) for x in ts).most_common())

print()
print("=== role|timestamp|content 完全相同的组 ===")
def key(e):
    return "%s|%s|%s" % (e.get("role", ""), e.get("timestamp", ""), e.get("content", ""))
c = Counter(key(e) for e in recs if isinstance(e, dict))
dups = [(k, n) for k, n in c.items() if n > 1]
print("   重复组数：%d，涉及记录：%d 条" % (len(dups), sum(n for _, n in dups)))
for k, n in dups[:8]:
    role, t, content = k.split("|", 2)
    print("   ×%d  [%s] %s  「%s」" % (n, role, t, content[:60]))

print()
print("=== 这些重复记录是否逐字节相同（除时间戳外有无差异）===")
groups = {}
for e in recs:
    if isinstance(e, dict):
        groups.setdefault(key(e), []).append(e)
diff = 0
for k, g in groups.items():
    if len(g) > 1:
        s = {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in g}
        if len(s) > 1:
            diff += 1
print("   完全相同的重复组：%d，字段有差异的重复组：%d" % (
    sum(1 for g in groups.values() if len(g) > 1) - diff, diff))
