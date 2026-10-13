# -*- coding: utf-8 -*-
"""修上一轮 ppt_reposition.py 留下的三处问题：
  ① 两句 quote 都被改成同一句（因为两个 quote 的 by 都以"定位：整合者"开头，走了同一分支）
     ⇒ 第 9 页 = 市场段收尾（新主张）；第 21 页 = 路线收束
  ② 第 10 页（section 02）的讲稿被写成"一句话概括定位"（那该是第 9 页的）
     ⇒ 第 10 页 = 承接句；第 9 页 = 讲那句主张
  ③ "并非首创"这句诚实说明应挂到第 8 页（它的最后一条 bullet 就是它），不当第 9 页的主讲稿
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")
NOTES = os.path.join(ROOT, "dev", "ppt", "notes.json")

o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
slides = o["slides"]
n = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read())
notes = n["notes"]

# ---------- ① 两句 quote 分开 ----------
quotes = [i for i, s in enumerate(slides) if s.get("type") == "quote"]
print("quote 页（1 起）:", [i + 1 for i in quotes])
if len(quotes) >= 2:
    first, last = quotes[0], quotes[-1]
    slides[first]["text"] = "大厂在给 AI 装一只宠物；我们做的是一个人"
    slides[first]["by"] = "她在办公线是吉祥物，在我们这儿是角色"
    slides[last]["text"] = "先让她真的住进电脑里，再让她走到你身边"
    slides[last]["by"] = "路线取舍：先做深关系，再谈形态自由"
    print("✓ ① 第 %d 页 = 市场段主张；第 %d 页 = 路线收束" % (first + 1, last + 1))

json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

# ---------- ②③ 讲稿归位 ----------
notes["8"] = ("这一页是把我们放进去比。六条里我们能同时给：形象、人格与记忆、聊天软件打通、"
              "真声线、桌面操作、手机端。\n"
              "最后那条“并非首创”我想主动说出来：我查到唯一把形象、聊天软件、本地操作、语音"
              "同时做齐且还在活跃的是 super-agent-party。这件事写在页面上，"
              "但它不是今天的开场——开场那句在下一页。")
notes["9"] = ("这句话是今天最想留下的一句：大厂在给 AI 装一只宠物，我们做的是一个人。\n"
              "腾讯、Anthropic、OpenAI 都在把宠物放进办公工具——宠物是入口、是身份锚点，"
              "但那是一只通用的猫。没有人负责回答“她还是不是她本人”。\n"
              "我们的全部工作都在这个问题上：固定的人格、固定的声线、跨端的长期记忆。")
notes["10"] = "下面进第二部分：她具体能做什么，以及这些是怎么实现的。"

n["notes"] = {k: v for k, v in sorted(notes.items(), key=lambda kv: int(kv[0])) if v}
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(
    json.dumps(n, ensure_ascii=False, indent=2))
print("✓ ②③ 已重挂第 8/9/10 页讲稿")

print()
print("=== 复核对齐表（第 1~11 页）===")
for i, s in enumerate(slides[:11], 1):
    t = s.get("title") or s.get("text") or "(无题)"
    print("%2d | %-28s | %s" % (i, t[:28], (n["notes"].get(str(i), "（无）"))[:44]))
