# -*- coding: utf-8 -*-
"""批量审 deck 里"具体到能指出代码"的断言。逐条给 判定 + 依据。

待审：
  A 第 14 页「状态页四个分类：状态 / 习惯 / 记忆 / 提醒」
  B 第 14 页「她自己会学：空闲时自己补课、归纳"关于主人的事"」
  C 第 13 页「装扮即数据：衣服/发型/装饰/姿势都是层号，换装=换层再合成」
  D 第 18 页「多角色：一套引擎跑多个角色，各有各的记忆与声音」
  E 第 15 页「手机端走同一套后端协议 / 共用同一份记忆」
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def read(rel):
    p = os.path.join(ROOT, rel)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def has(rel, pat):
    return bool(re.search(pat, read(rel)))


def show(rel, pat, n=3):
    out = []
    for i, l in enumerate(read(rel).split("\n"), 1):
        if re.search(pat, l):
            out.append("      %s:%d| %s" % (rel, i, l.strip()[:96]))
            if len(out) >= n:
                break
    return out


print("=== A 状态页四个分类（状态/习惯/记忆/提醒）===")
for rel in ("pcl_launcher/status_panel.py",):
    for pat in (r'addTab|QTabWidget|"状态"|"习惯"|"记忆"|"提醒"'):
        for line in show(rel, pat, 4):
            print(line)

print()
print("=== B 空闲时自己补课 / 归纳关于主人的事 ===")
for rel in ("tool/self_learn.py", "tool/state.py", "main.py", "run.py"):
    if not os.path.isfile(os.path.join(ROOT, rel)):
        continue
    for line in show(rel, r"self_learn|补课|自学|归纳|关于主人", 3):
        print(line)
print("   自学日志文件：", "存在 ✓" if os.path.isfile(os.path.join(ROOT, "data", "self_learn.log")) else "不存在 ✗")
if os.path.isfile(os.path.join(ROOT, "data", "self_learn.log")):
    sz = os.path.getsize(os.path.join(ROOT, "data", "self_learn.log"))
    print("     大小 %.0f KB" % (sz / 1024))
    ls = io.open(os.path.join(ROOT, "data", "self_learn.log"), encoding="utf-8",
                 errors="replace").read().split("\n")
    print("     末行：", (ls[-2] if len(ls) > 1 else ls[-1])[:110])

print()
print("=== C 装扮即数据（层号 / normalize_layers / 合成）===")
for line in show("tool/portrait_outfit.py", r"def normalize_layers|def save_outfit|层号|layers", 4):
    print(line)

print()
print("=== D 多角色（一套引擎跑多个角色）===")
pets = os.path.join(ROOT, "pets")
if os.path.isdir(pets):
    for d in sorted(os.listdir(pets)):
        sub = os.path.join(pets, d)
        if os.path.isdir(sub):
            has_pet = os.path.isfile(os.path.join(sub, "pet.json"))
            has_voice = os.path.isdir(os.path.join(sub, "voices"))
            has_mem = os.path.isdir(os.path.join(sub, "memory"))
            print("     角色 %-12s pet.json=%s voices=%s memory=%s"
                  % (d, "✓" if has_pet else "✗", "✓" if has_voice else "✗",
                     "✓" if has_mem else "✗"))

print()
print("=== E 手机端与桌面端共用记忆文件 ===")
chat = r"E:\university\order\python\pet\chatter"
for rel in ("app/src/main/java/com/aipet/murasame/bot/chat/MemoryStore.kt",):
    p = os.path.join(chat, rel)
    if os.path.isfile(p):
        for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().split("\n"), 1):
            if re.search(r"long_history|history\.json|memory", l):
                print("      %s:%d| %s" % (rel.split("/")[-1], i, l.strip()[:92]))
