# -*- coding: utf-8 -*-
"""让 deck 的"互动"页贴合**当前实现**（原来把已完成的事写成了中期规划）。

事实（本轮实现并验证过的）：
  · 手机端已接入 MediaPipe HandLandmarker（21 关键点），相机帧 → 关键点 → 命中她 → 反应
  · 已实现：视线跟随（__lookAt）/ 捏合=捏脸（__pinch）/ 握拳 / 挥手（__wave）
  · 验证：assembleDebug + testDebugUnitTest 通过；HandGestureTest 21 个用例（9 捏合 + 6 握拳 + 6 挥手）
  · **未验证**：真机上"手伸过去她眼睛真的跟着转吗"—— 必须在真机确认，如实标注
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

for s in slides:
    if s.get("title", "").startswith("中期：让互动更自然"):
        s["title"] = "互动：从「看着你」到「看懂你」（已落地一半）"
        s["bullets"] = [
            {"text": "已实现：手部 21 关键点检测",
             "sub": "手机端接入 MediaPipe HandLandmarker；相机帧 → 关键点 → 命中她 → 反应，链路已通"},
            {"text": "已实现：视线跟随",
             "sub": "她自己「看着你的手」——关键点换算到屏幕后驱动 3D 角色的视线目标"},
            {"text": "已实现：三个手势",
             "sub": "捏合=捏脸、握拳、挥手；各自独立判定与去抖（21 个单测：9 捏合 + 6 握拳 + 6 挥手）"},
            {"text": "下一步：更多手势 + 接进对话",
             "sub": "比心 / 指向某处；挥手时顺便触发一句问候，把动作和她的性格连起来"},
            {"text": "⚠ 还没做的：真机调优",
             "sub": "编译与单测都过了，但「真手伸过去她眼睛是否跟着转」必须真机确认；"
                    "偏差只调相机朝向与镜像，不动已固定住的检测与坐标层"},
        ]
        print("✓ 已重写第 19 页（互动）")
        break

# 第 18 页"近期"补一句：手机端的这些能力已经写出来了，近期要做的其实是真机验证与调优
for s in slides:
    if s.get("title", "").startswith("近期：把体验做扎实"):
        s["bullets"] = [
            {"text": "手机端：真机验证与调优",
             "sub": "功能已写好（含手部互动），近期重点是插上真机跑全链路并调准相机参数"},
            {"text": "形象扩展",
             "sub": "3D 模型方案评估（先验证能不能跑起来，再谈建模成本）"},
            {"text": "多角色",
             "sub": "一套引擎跑多个角色，各有各的记忆与声音"},
        ]
        print("✓ 已更新第 18 页（近期）")
        break

json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

# 讲稿同步
n = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read())
notes = n["notes"]
for i, s in enumerate(slides, 1):
    t = s.get("title", "")
    if t.startswith("互动：从"):
        notes[str(i)] = ("这一页要说得实在：手部互动我已经做出来一半了。"
                         "手机端接了 21 个关键点的手部检测，链路是通的——她会看着你的手；"
                         "还做了三个手势：捏合（捏脸）、握拳、挥手，一共 21 个单元测试。\n"
                         "但我要说清楚：**这些只到「编译和单测通过」**，"
                         "真手伸过去她的眼睛是不是真的跟着转，必须真机上确认。"
                         "所以这一页既是成果，也是下一步的清单。")
    elif t.startswith("近期：把体验做扎实"):
        notes[str(i)] = ("近期三件事：手机端的真机验证与调优（功能已经写好了）、"
                         "3D 模型方案评估（先验证能不能跑起来，再谈建模成本）、多角色支持。")
    elif t.startswith("中期：更省算力"):
        notes[str(i)] = ("另一条中期的路是毫米波雷达：不依赖光线和镜头、隐私友好、能全天运行。"
                         "这里要诚实：毫米波做隐私友好交互已经有人做了（今年 9 月的 mmHRI，"
                         "隔着帘子做机器人操作，动作识别 85%），所以我们不主张「第一次用毫米波」。"
                         "我们的问题不同——他们做操纵、指标是准确率；我们做陪伴、指标是"
                         "关系感知和打扰容忍度。这条线能不能立住，取决于接下来的用户研究。")
n["notes"] = {k: v for k, v in sorted(notes.items(), key=lambda kv: int(kv[0])) if v}
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(
    json.dumps(n, ensure_ascii=False, indent=2))
print("✓ 讲稿已同步（互动页 / 近期页 / 毫米波页）")

print()
print("=== 复核第 18~19 页 ===")
for i, s in enumerate(slides, 1):
    if i in (18, 19):
        print("--- 第 %d 页: %s ---" % (i, s.get("title")))
        for b in s.get("bullets", []):
            print("   · %s — %s" % (b.get("text"), (b.get("sub") or "")[:76]))
        print("   讲稿: %s" % (n["notes"].get(str(i)) or "")[:150])
