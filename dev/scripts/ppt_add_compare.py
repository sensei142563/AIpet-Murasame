# -*- coding: utf-8 -*-
"""在"我们的位置"之后插一页 two_col 对照（他们 vs 我们），并把讲稿整体后移重挂。
引擎只支持 title/section/content/two_col/quote/end（无 table），two_col 是这里最好的载体。
顺序：改 outline → 重挂 notes → 打印对齐表（重建与渲染由下一条命令做）。
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

table = {
    "type": "two_col",
    "title": "同一个「宠物」位置，两种完全不同的做法",
    "left_title": "他们：办公 / 生产力线",
    "left": [
        {"text": "宠物是通用吉祥物", "sub": "一只猫、一只随机孵化的宠物；OpenAI 还允许自建 Custom Pet"},
        {"text": "目标是任务", "sub": "替你翻译、整理、跑代码、跨应用执行（WorkBuddy 想做“Agent 时代的操作系统”）"},
        {"text": "指标是效率与留存", "sub": "识别率、任务成功率、次日留存"},
        {"text": "不要求“是她本人”", "sub": "所以换皮、联名、装扮都不影响产品成立"},
        {"text": "场景：办公桌 / 公共场所", "sub": "mmHRI 这类研究甚至以医院病房、餐厅为例"},
    ],
    "right_title": "我们：角色 / 关系线",
    "right": [
        {"text": "角色是具体的人", "sub": "固定人设不 OOC、角色专属 GPT-SoVITS 声线、Live2D + 2D 双形态"},
        {"text": "目标是关系", "sub": "长期记忆、习惯、日记、关系值 —— 按真实相处证据抬升，不靠嘴甜"},
        {"text": "指标是关系感知与打扰容忍度", "sub": "她该不该开口、什么时候该安静，是核心体验问题"},
        {"text": "人格连续性是核心变量", "sub": "换角色 = 换一个人，而不是换一张皮"},
        {"text": "场景：桌面 + 手机里的日常", "sub": "QQ / 微信桥接同一套人设与记忆，手机端共用同一份记忆文件"},
    ],
}

# 插到"我们的位置"之后
idx = None
for i, s in enumerate(slides):
    if s.get("title", "").startswith("我们的位置"):
        idx = i + 1
        break
if idx is None:
    print("✗ 没找到锚点页")
    sys.exit(1)
if any(s.get("title", "").startswith("同一个「宠物」位置") for s in slides):
    print("· 已存在该页")
else:
    slides.insert(idx, table)
    print("✓ 已插入对照页（新第 %d 页）" % (idx + 1))

json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

# 讲稿：1..8 不变；新 9 = 对照页新讲稿；新 10.. ← 旧 9..
new_notes = {}
for i in range(1, idx + 1):
    if str(i) in notes:
        new_notes[i] = notes[str(i)]
new_notes[idx + 1] = ("同一件事，两种做法，放在一起看最清楚。\n"
                      "左边是办公线：宠物是通用吉祥物，目标是任务，指标是效率和留存——"
                      "所以换皮、联名都不影响产品成立。\n"
                      "右边是我们：角色是具体的人，人格连续性是核心变量，"
                      "指标是关系感知和打扰容忍度。这一页就是回答“有什么是我们有、别人没有的”。")
# 旧的 9.. 顺移一位
old_keys = sorted((int(k) for k in notes), reverse=True)
for k in old_keys:
    if k >= idx + 1:
        new_notes[k + 1] = notes[str(k)]

n["notes"] = {str(k): v for k, v in sorted(new_notes.items()) if v}
n["_comment"] = ("每页的讲稿（备注）。key = 页码（1 起）。口语化、每页 2~4 句。"
                 "2026-10-13 二次重挂：新增“他们 vs 我们”对照页后整体后移一位；"
                 "此前已修掉第 3~19 页错位一格的问题。"
                 "两份开场（创业版 / 学术版）见 dev/docs/导师反馈拆解与定位建议-2026-10-13.md。")
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(json.dumps(n, ensure_ascii=False, indent=2))
print("✓ 已重挂讲稿，条数 =", len(n["notes"]))

print()
print("=== 对齐表（第 1~12 页）===")
for i, s in enumerate(slides[:12], 1):
    t = s.get("title") or s.get("text") or "(无题)"
    print("%2d | %-34s | %s" % (i, t[:34], (n["notes"].get(str(i), "（无）"))[:38]))
print("… 总页数 =", len(slides))
