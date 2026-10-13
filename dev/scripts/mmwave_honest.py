# -*- coding: utf-8 -*-
"""毫米波补充检索的结论 + 据此把 deck 第 20 页（毫米波）改成诚实版。

结论（都有出处）：
  · mmHRI（arXiv:2609.34220）—— 毫米波 + 隐私友好 HRI，但场景是**机器人操纵**
  · 文心守护（CSDN 2025-11-23，AI Studio 开源）—— 60GHz 毫米波 + 文心智能体，
    明说做**「健康分析与情感陪伴」**，口号「**存在即感知**」，对象是**独居老人看护**
  · 居家步速测量（TechRxiv）—— 雷达测居家健康指标
⇒ "毫米波 + 陪伴"**已经有人做过**，不能主张首创。
   仍可能不同的是：**对象（二次元角色 vs 老人看护）、形态（她住在桌面/手机/IM vs 壁挂传感+App）、
   目标与指标（关系与打扰 vs 安全告警与健康指标）、以及"角色人格连续性"这个变量**。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")
NOTES = os.path.join(ROOT, "dev", "ppt", "notes.json")

# ---------- ① deck 第 20 页改成诚实版 ----------
o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
slides = o["slides"]
for s in slides:
    if s.get("title", "").startswith("中期：更省算力"):
        s["title"] = "中期：另一条感知路线（毫米波）——已有人做，我们做个窄的"
        s["bullets"] = [
            {"text": "为什么看这条路", "sub": "不依赖光线与镜头、隐私友好、可全天运行；"
                                          "作为「她在不在、在做什么」的输入很合适"},
            {"text": "但已经有人做了（一）", "sub": "mmHRI：毫米波做隐私友好人机交互，"
                                               "隔帘做机器人操作、动作识别 85%（2026-09）"},
            {"text": "但已经有人做了（二）", "sub": "文心守护：60GHz 雷达 + 文心智能体，"
                                               "明说做「健康分析与情感陪伴」，口号「存在即感知」，"
                                               "面向独居老人看护（开源）"},
            {"text": "所以我们不主张「首创」", "sub": "不写「第一次用毫米波做陪伴」——"
                                                 "那两处已占，写了会被当场问倒"},
            {"text": "我们要做的那一小块", "sub": "变量换成**角色的人格连续性**，"
                                              "指标换成**关系感知与打扰容忍度**；"
                                              "对象是二次元角色，形态是她住在桌面/手机/IM 里"},
            {"text": "怎么走", "sub": "课题装置输出标准化参数流 → 先在桌面端驱动她 → 需要时再上手机；"
                                   "先做用户研究，不先堆硬件"},
        ]
        print("✓ ① 已把第 20 页改为诚实版（含两处已有工作）")
        break
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

# ---------- ② 讲稿同步 ----------
n = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read())
for i, s in enumerate(slides, 1):
    if s.get("title", "").startswith("中期：另一条感知路线"):
        n["notes"][str(i)] = (
            "另一条感知路线是毫米波雷达：不依赖光线和镜头、隐私友好、能全天运行。"
            "但这里必须诚实——**已经有人做了**：一是 mmHRI，毫米波做隐私友好人机交互，"
            "隔着帘子做机器人操作，动作识别 85%；二是「文心守护」，60GHz 雷达 + 大模型，"
            "人家明说做『健康分析与情感陪伴』，口号就是『存在即感知』，而且是开源的。\n"
            "所以我们**不主张首创**。我们想做窄的那一块：把变量换成**角色的人格连续性**，"
            "把指标换成**关系感知与打扰容忍度**，对象是二次元角色、形态是她住在桌面和手机里。"
            "这条路先做用户研究，不先堆硬件。")
        print("✓ ② 讲稿已同步")
        break
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(
    json.dumps(n, ensure_ascii=False, indent=2))

# ---------- ③ 记进调研文档 ----------
R = os.path.join(ROOT, "docs", "大厂入局与对标补查-2026-10-13.md")
t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
ADD = """

---

## 九、毫米波补充检索（2026-10-13）：**"毫米波 + 陪伴"已有人做**

上一节我说"是否已有人把毫米波用于居家/情感陪伴：本次只查到机器人操纵与智能环境手势，
写『据我们所知还没有人……』之前必须再做一轮针对性检索"。**做完了，结论是不能那么写。**

| 已有工作 | 做了什么 | 与我们的关系 |
|---|---|---|
| **文心守护**（CSDN 2025-11-23；AI Studio 全量开源，Apache-2.0） | 60GHz 毫米波雷达采点云 → 边缘 C++/ESP32 → 云端**文心智能体**做**健康分析与情感陪伴**；口号是「**去图像化 / 去穿戴化 / 存在即感知**」；目标是独居老人**居家安全**（跌倒检测为第一位）；含 PaddlePaddle 跌倒模型与 Gradio 大屏 | ⚠ **最接近的一个**：雷达 + LLM + "情感陪伴" + "存在即感知" 全占了。**不能主张首创。** |
| **mmHRI**（arXiv:2609.34220，2026-09） | 毫米波双流 + 记忆状态空间模型 → 人体动作/姿态 → 驱动 VLA 做机器人操作；拉帘遮挡下动作识别 85.09% | 说明该模态**技术可行**；场景是**操纵**不是陪伴 |
| 居家步速测量（TechRxiv） | 雷达**无感测量居家步速**，探索长期健康指标 | 属"雷达 + 居家健康监测"那一类 |
| 检索范围说明 | 关键词涵盖 mmWave + companion / ambient agent / presence / wellbeing / 情感陪伴 / 独居 / 老人 等 | 以下是**本次检索范围内**的结论，不等于穷尽 |

### 因此可写的、与不可写的
- ✗ **不可写**："第一次把毫米波用于陪伴"、"据我们所知还没人做过"；
- ✓ **可写**（且已在 deck 第 20 页改成这个口径）：**变量与指标不同** ——
  已有工作以**看护/操纵**为目标（指标：识别率、任务成功率、健康指标），
  办公线以**任务**为目标（指标：效率、留存）；
  **我们把「角色的人格连续性」当变量、把「关系感知与打扰容忍度」当指标**，
  对象是二次元角色、形态是她住在桌面与手机里。
  这一层在本次检索范围内**未见对应工作** —— 但仍以"我们关注的问题是……"起句，
  不写"据我们所知没人做过"。
- 数字与出处：文心守护原文自述目标为"2.8 亿老人"、路线为"端-边-云"、
  开源地址在百度 AI Studio（项目名"康护宝"）。

### 对 PPT 的影响（已落实）
deck 第 20 页由"毫米波雷达 / 已有可复用装置 / 迁移方向"三条**乐观叙述**，
改为**六条诚实版**：为什么看这条路 → 已有工作（一）mmHRI → 已有工作（二）文心守护 →
所以不主张首创 → 我们要做的那一小块 → 怎么走（先参数流、先用户研究，不先堆硬件）。
讲稿同步重写。
"""
if "毫米波补充检索（2026-10-13）" not in t:
    io.open(R, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ ③ 已把结论写进 docs/大厂入局与对标补查")

MSG = """docs(research)+docs(ppt): 毫米波补充检索 —— "毫米波+陪伴"已有人做（文心守护），据此把第 20 页改成诚实版

## 检索结论（都有出处）
- **文心守护**（CSDN 2025-11-23；AI Studio 全量开源 Apache-2.0）：
  60GHz 毫米波点云 + 边缘 C++（ESP32/C1001）+ 云端**文心智能体**，
  原文自述做"健康分析与**情感陪伴**"，口号"去图像化 / 去穿戴化 / **存在即感知**"，
  目标独居老人**居家安全**（跌倒检测第一位），含 PaddlePaddle 跌倒模型与 Gradio 大屏。
- **mmHRI**（arXiv:2609.34220，2026-09）：毫米波隐私友好 HRI —— 场景是**机器人操纵**，识别 85.09%。
- 居家步速测量（TechRxiv）：雷达无感测居家健康指标。

⇒ **不能主张首创**：雷达 + LLM + "情感陪伴" + "存在即感知" 已被占（文心守护最接近）。
⇒ 仍可能不同：**对象**（二次元角色 vs 老人看护）、**形态**（住在桌面/手机/IM vs 壁挂传感+App）、
   **目标与指标**（关系与打扰 vs 安全告警与健康指标）、以及**"角色人格连续性"这个变量**。

## 据此改了 deck 第 20 页（原来是乐观叙述）
旧：毫米波雷达 / 已有可复用装置 / 迁移方向（三条，读起来像"我们来做这条路"）
新：**六条诚实版** —— 为什么看这条路 → 已有工作（一）mmHRI → 已有工作（二）文心守护 →
**所以我们不主张「首创」** → 我们要做的那一小块（变量=人格连续性，指标=关系与打扰）→
怎么走（课题装置输出参数流 → 先桌面端 → 需要时再上手机；先用户研究，不先堆硬件）。
讲稿同步重写。

## 为什么这轮值钱
导师最重的一句是"有些问题别人已经解决了"。**与其在答辩现场被问倒，
不如我们自己先把这两处查出来、写在页面上，给出"那我们做哪一块"。**
（这也是今天第二次同型收获：上一次是 mmHRI，这次是文心守护。）

## 顺带
结论与出处已写进 `docs/大厂入局与对标补查-2026-10-13.md` 第九节，含"检索范围说明"
（本次检索范围内未见对应工作 ≠ 穷尽），避免以后有人把"没查到"当成"不存在"。
"""
p = os.path.join(MAP, "_msg_mmwave2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n2 = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n2, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
