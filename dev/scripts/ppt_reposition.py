# -*- coding: utf-8 -*-
"""重写 PPT 的开场与定位，并**修掉讲稿错位**：
  ① outline 插入 1 页「大厂入局时间线」（放在 section 01 之后）
  ② 重写"横向对比"页：把主张放前面（办公线做任务 / 我们做关系），把"并非首创"降为证据之一
  ③ 重写收束页：> 大厂在给 AI 装一只宠物；我们做的是一个人。
  ④ notes 逐页**按内容**重挂（修掉第 3~19 页整体错位一格），并为新页/改写页写新讲稿
  ⑤ 打印最终对齐表供人工核对
不做：不碰引擎（build_deck.py 等），只改 outline/notes 这一层。
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
old_notes = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read())["notes"]

# ---------- ① 新页：大厂入局时间线 ----------
timeline = {
    "type": "content",
    "title": "2026：大厂集体入局，但走的是同一条线",
    "bullets": [
        {"text": "2026-04　Anthropic", "sub": "Claude Code 加虚拟宠物 Buddy —— 陪着写代码"},
        {"text": "2026-04　元空AI（仓鼠元元）", "sub": "自称“中国首个 AI 办公桌宠”，定位办公效率：划词即用、常驻多轮对话"},
        {"text": "2026-05　腾讯 WorkBuddy", "sub": "上线养成玩法：积分 / 盲盒 / 装扮 / 派它去旅行"},
        {"text": "2026-09　腾讯 ×《和平精英》", "sub": "Buddy 猫穿上游离子皮肤；开放平台首批 100+ 伙伴、10+ 品类"},
        {"text": "2026-03　PetClaw", "sub": "自称 24 小时桌面伴侣：跨应用替你做事 + 长期记忆"},
        {"text": "读法：全部是「办公 / 生产力 + 一只通用宠物」",
         "sub": "它们要的是任务；宠物是入口、是身份锚点 —— 但没有人负责回答“她是不是她本人”"},
    ],
}
# 插到 section 01（第 2 页）之后
if not any(s.get("title", "").startswith("2026：大厂集体入局") for s in slides):
    slides.insert(2, timeline)
    print("✓ ① 已插入「大厂入局时间线」（新第 3 页）")

# ---------- ② 重写"横向对比"页 ----------
for s in slides:
    if s.get("title", "").startswith("横向对比"):
        s["title"] = "我们的位置：办公线做「任务」，我们做「关系」"
        s["bullets"] = [
            {"text": "主张", "sub": "把「角色的人格连续性」当变量：她是不是她本人、还记不记得你"},
            {"text": "对照：办公线", "sub": "腾讯 / Anthropic / OpenAI / 仓鼠元元的宠物是通用吉祥物，指标是效率与留存"},
            {"text": "形象", "sub": "Live2D + 2D 立绘双形态，可换装、随情绪联动；QQ 侧与桌宠同一套装扮"},
            {"text": "人格与记忆", "sub": "固定人设不 OOC、角色专属 GPT-SoVITS 声线、长期记忆与关系值（按相处证据抬升）"},
            {"text": "出桌面", "sub": "QQ / 微信桥接同一套人设与记忆；手机端共用同一套协议与记忆文件"},
            {"text": "桌面操作", "sub": "键鼠 / 看屏幕 / 文件只读访问 —— 能做事的角色，而不是只会聊天的窗口"},
            {"text": "诚实边界", "sub": "并非首创：唯一查到把这几条同时做齐且活跃的是 super-agent-party（详见备注）"},
        ]
        print("✓ ② 已重写「横向对比」页")
        break

# ---------- ③ 重写收束页 + 第 8 页的 quote 定位 ----------
for s in slides:
    if s.get("type") == "quote" and "住在电脑里的人" in s.get("text", ""):
        if s.get("by", "").startswith("定位：整合者"):
            # 第 8 页（市场部分收尾）换成新主张
            s["text"] = "大厂在给 AI 装一只宠物；我们做的是一个人"
            s["by"] = "定位：她的“人格连续性”，是办公线结构性地不需要的东西"
            print("✓ ③a 已改写市场段收尾那句 quote")
        else:
            s["text"] = "先让她真的住进电脑里，再让她走到你身边"
            print("✓ ③b 已改写路线收束页")

o["subtitle"] = ("会长期陪伴的桌面智能体：有形象 · 会记事 · 能干活 · 还能上手机"
                 "　｜　主张：办公线做任务，我们做关系")
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
print("✓ 已写回 outline.json，页数 =", len(slides))

# ---------- ④ notes 按内容重挂 ----------
# 旧讲稿（1..21）。旧 2..19 讲的是"下一页"的内容（错位一格），现按语义归位。
old = {int(k): v for k, v in old_notes.items()}

new_notes = {}
new_notes[1] = old.get(1, "")                                   # 标题
new_notes[2] = old.get(2, "")                                   # section 01 桌宠市场
new_notes[3] = ("这里先给一个时间线，说明这波不是我们自己在想：2026 年 3 月到 9 月，"
                "腾讯、Anthropic、OpenAI、还有北大的仓鼠元元，全部在做桌宠。"
                "但请注意它们走的是同一条线——办公和生产力，宠物是入口、是身份锚点。"
                "没有一个人负责回答“她还是不是她本人”。这句话是今天整个故事的支点。")
new_notes[4] = ("市面上的做法可以分四类：开源桌宠、Steam 商业桌宠、AI 桌宠新秀，"
                "以及像《你妈》这种靠话题出圈的。下面逐类看它们强在哪、缺什么。")
new_notes[5] = old.get(3, "")                                   # 开源（旧3）
new_notes[6] = old.get(4, "")                                   # Steam（旧4）
new_notes[7] = old.get(5, "")                                   # AI 聊天机器人（旧5）
new_notes[8] = old.get(6, "")                                   # 横向对比（旧6）
new_notes[9] = ("强调一句：我们并非首创。我查到唯一把形象、聊天软件、本地操作、语音"
                "同时做齐且还在活跃的是 super-agent-party。这一点我写在备注里，"
                "但它不是开场要讲的东西——开场讲的是“办公线做任务，我们做关系”。")
new_notes[10] = old.get(8, "")                                  # quote 收尾（旧8）
# 其后整体后移一位：新 11..22 ← 旧 9..21
for i in range(11, len(slides) + 1):
    new_notes[i] = old.get(i - 1, "")
# 未来规划那页（新 20 = 旧 19 的毫米波）讲稿更新为新查证结论
for i, s in enumerate(slides, 1):
    if s.get("title", "").startswith("中期：更省算力"):
        new_notes[i] = ("另一条中期的路是毫米波雷达：不依赖光线和镜头、隐私友好、能全天运行。"
                        "这里要诚实：毫米波做隐私友好交互已经有人做了（今年 9 月的 mmHRI，"
                        "隔着帘子做机器人操作，动作识别 85%），所以我们不主张“第一次用毫米波”。"
                        "我们的问题不同——他们做操纵、指标是准确率；我们做陪伴、指标是"
                        "关系感知和打扰容忍度。这条线能不能立住，取决于接下来的用户研究。")
    if s.get("title", "").startswith("近期：把体验做扎实"):
        new_notes[i] = ("近期三件事：手机端对齐与优化、3D 模型方案评估（建模成本要算清楚，"
                        "先验证再投入）、多角色支持。")

payload = {
    "_comment": ("每页的讲稿（备注）。key = 页码（1 起）。口语化、每页 2~4 句，照着念即可。"
                 "2026-10-13 重挂：修掉此前第 3~19 页整体错位一格的问题；"
                 "并新增时间线页、改写定位页与路线收束页的讲稿。"
                 "两份开场（创业版 / 学术版）见 dev/docs/导师反馈拆解与定位建议-2026-10-13.md。"),
    "notes": {str(k): v for k, v in sorted(new_notes.items()) if v},
}
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(
    json.dumps(payload, ensure_ascii=False, indent=2))
print("✓ ④ 已重写 notes.json，条数 =", len(payload["notes"]))

# ---------- ⑤ 对齐表 ----------
print()
print("=== 最终对齐表（页 / 标题 / 讲稿首句）===")
for i, s in enumerate(slides, 1):
    t = s.get("title") or s.get("text") or "(无题)"
    txt = payload["notes"].get(str(i), "（无讲稿）")
    print("%2d | %-30s | %s" % (i, t[:30], txt[:46]))
