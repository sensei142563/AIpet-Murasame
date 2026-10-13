# -*- coding: utf-8 -*-
"""精确审 deck 断言（只打关键行，不做宽泛匹配）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def lines_with(rel, pat, limit=8):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return ["      ✗ 文件不存在: " + rel]
    out = []
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(pat, l):
            out.append("      %s:%d| %s" % (os.path.basename(rel), i, l.strip()[:100]))
            if len(out) >= limit:
                break
    return out or ["      （无匹配：%s）" % pat]


print("=== A 状态页的页签（只看 addTab）===")
for l in lines_with("pcl_launcher/status_panel.py", r"addTab\("):
    print(l)

print()
print("=== A2 status_snapshot 提供了哪几块数据 ===")
for l in lines_with("tool/status_snapshot.py", r"^\s*(\"|')?(状态|习惯|记忆|提醒)|def .*snapshot|return \{", 10):
    print(l)

print()
print("=== B 自学：谁写 self_learn.log、写了什么 ===")
for l in lines_with("tool/self_learn.py", r"self_learn\.log|def |归纳|关于主人|补课", 8):
    print(l)
p = os.path.join(ROOT, "data", "self_learn.log")
if os.path.isfile(p):
    ls = [x for x in io.open(p, encoding="utf-8", errors="replace").read().split("\n") if x.strip()]
    print("      日志存在 ✓ %.0f KB，%d 行" % (os.path.getsize(p) / 1024, len(ls)))
    for x in ls[-3:]:
        print("      末几行：", x[:104])

print()
print("=== C 装扮即数据（层号/合成）===")
for l in lines_with("tool/portrait_outfit.py", r"^def |层号|normalize_layers", 8):
    print(l)

print()
print("=== D 多角色（pets/ 下有哪几个角色包）===")
pets = os.path.join(ROOT, "pets")
if os.path.isdir(pets):
    for d in sorted(os.listdir(pets)):
        sub = os.path.join(pets, d)
        if os.path.isdir(sub):
            def _y(n):
                return "✓" if os.path.exists(os.path.join(sub, n)) else "✗"
            print("      %-12s pet.json=%s voices=%s memory=%s live2d=%s fgimages=%s"
                  % (d, _y("pet.json"), _y("voices"), _y("memory"), _y("live2d"), _y("fgimages")))

print()
print("=== E 手机端记忆文件与桌面端同名同构 ===")
MS = r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame\bot\chat\MemoryStore.kt"
if os.path.isfile(MS):
    for i, l in enumerate(io.open(MS, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if re.search(r"long_history|history\.json|journal|memory", l):
            print("      MemoryStore.kt:%d| %s" % (i, l.strip()[:96]))
else:
    print("      ✗ 找不到 MemoryStore.kt")
