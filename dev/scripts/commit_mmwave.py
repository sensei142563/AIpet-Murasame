# -*- coding: utf-8 -*-
"""把毫米波那条"待查"变成"已查"，并**修正**原先的设想：
   已有人做"毫米波 + 隐私友好 HRI"（mmHRI），所以我们不能主张"第一次用毫米波"；
   但问题域不同（他们是机器人操纵/公共场所，我们是居家长期陪伴），
   于是把主张收窄成"把毫米波用在陪伴而非操纵上，并研究它对关系感知与打扰边界的影响"。
   同时把 mmHRI 从"竞争者"改用作"可行性背书"。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
D = os.path.join(ROOT, "docs", "大厂入局与对标补查-2026-10-13.md")

ADD = """

---

## 八、毫米波那条"待查"已查 —— **需要修正我们的设想**（2026-10-13 补）

原文第四节第 4 条写的是"非摄像头感知（毫米波）：**潜在最强（待查）**"。现在查完了，
结论是**不能按原来的方式讲**。

### 查到的事实

**mmHRI: Towards Privacy-Preserving Human-Robot Interaction with Millimeter-Wave Radar**
（arXiv:2609.34220，2026-09-28，cs.RO，作者来自机器人/具身方向团队）

- **动机与我们高度重合**：现有 HRI 系统依赖 RGB 相机持续观察人（如手势），
  在医院病房、餐厅这类**隐私敏感场所**不允许摄像头直拍；
- **做法**：毫米波雷达 + **双流架构**（未滤波的原始雷达张量 + 雷达点云）联合估计
  人的**动作与 3D 姿态**；再用 **基于记忆的状态空间模型（MSSM）**保留历史雷达特征，
  缓解雷达数据的稀疏性与时间不一致；把估计出的人体状态转成**结构化文本指令**，
  驱动一个 **VLA（视觉-语言-动作）策略**做闭环操作；
- **结果**：在"拉帘遮挡"的隐私保护设定下，动作识别 **85.09%**，优于既有雷达方案；
  机器人在**视觉被遮挡**的情况下完成递送与取物，跨未见过被试/杂乱布局/环境仍稳定；
- **自我定位**："the **first** multi-modal robot manipulation framework that achieves
  mmWave radar-guided privacy-preserving HRI"。

来源：[arXiv:2609.34220](https://arxiv.org/abs/2609.34220) ·
另见 [Quectel AM162AA-CS 毫米波 AiP 雷达模组](https://www.quectel.com.cn/news-and-pr/aip-radar-module)
（说明这类硬件**已经能买到现在成的模组**，做原型不必自研射频）。

### 因此必须修正两点

**修正一：不能主张"第一次把毫米波用于隐私友好交互"** ✗
这句话已经被 mmHRI 占了。硬写上去会被当场问倒 —— 这正是导师说的
"有些问题别人已经解决了"。

**修正二：把 mmHRI 从"竞争者"改用作"可行性背书"** ✓
它证明了**这条技术路线本身成立**（穿透遮挡、无需影像、精度可用）。
对我们而言，这比"没人做过"更有用：我们不必自证"毫米波能不能用"，
可以直接引用它，然后专注于**我们自己的问题**。

### 那我们自己的问题是什么（收窄后的主张）

mmHRI 的场景是**公共场所的机器人操纵**（递送/取物），目标是**替人做事**；
我们的场景是**居家的长期陪伴**，目标是**与人相处**。两者的研究问题不同：

| | mmHRI | 我们（收窄后） |
|---|---|---|
| 场所 | 医院病房 / 餐厅等隐私敏感公共空间 | **家里 / 桌面**（长时间、单人、低动作幅度） |
| 目标 | 手势 → 指令 → 机器人操作（**做事**） | 在场与状态感知 → **陪伴与恰当的打扰**（**相处**） |
| 关键指标 | 动作识别准确率、任务成功率 | **关系感知、打扰容忍度、长期可用性** |
| 感知对象 | 大幅度动作、3D 姿态 | **久坐场景的微小活动、在场/离席、作息节律** |

⇒ 可写成的研究问题（面向 UbiComp/IMWUT、CHI、CSCW 的写法）：

> **当一个陪伴型智能体能"感知到你在不在、在做什么"，而它的感知不依赖摄像头时，
> 用户对它的关系感知与打扰容忍度会如何变化？**
> 与已有工作（把雷达用于**操纵**、以准确率为指标）不同，
> 我们把它用于**陪伴**，并以**关系与打扰**为指标。

这个主张有三个好处：
1. **不撒谎**：不声称首创技术路线；
2. **可证伪**：能用用户研究做（而不是只能演示）；
3. **正对导师指路**：HCI 会议最吃的就是"新模态 + 关系/打扰"这类问题。

### 仍然要老实标"未查"的
- 是否**已经有人**把毫米波用于**居家陪伴/情感陪伴**场景？本次只查到机器人操纵与
  智能环境手势这两类。**在写出"据我们所知还没有人……"之前，必须再做一轮针对性检索**
  （关键词建议：mmWave + companion / ambient agent / presence awareness / home / wellbeing）。
- 外部装置的具体参数与输出格式 —— 需要确认后才能写进方案。
"""

t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "毫米波那条\"待查\"已查" not in t and "毫米波那条“待查”已查" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 已追加第八节（毫米波查证与主张修正）")
else:
    print("· 已有该节")

MSG = """docs(research): 毫米波那条已查 —— ⚠ 修正主张：不能声称"第一次用毫米波"

## 查到的事实
`mmHRI: Towards Privacy-Preserving Human-Robot Interaction with Millimeter-Wave Radar`
（arXiv:2609.34220，2026-09-28，cs.RO）：
· 动机与我们几乎重合：现有 HRI 依赖 RGB 相机持续观察人（手势等），
  而医院病房/餐厅等隐私敏感场所不允许摄像头直拍；
· 做法：毫米波雷达双流（原始张量 + 点云）估计人体**动作与 3D 姿态**，
  用基于记忆的状态空间模型（MSSM）缓解雷达稀疏/时间不一致，
  再把人体状态转成**结构化文本指令**驱动 VLA 策略做闭环机器人操作；
· 结果：拉帘遮挡设定下动作识别 **85.09%**，优于既有雷达方案；视觉被遮挡时仍能递送/取物；
· 自我定位："the **first** multi-modal robot manipulation framework that achieves
  mmWave radar-guided privacy-preserving HRI"。
另：Quectel AM162AA-CS 毫米波 AiP 雷达模组已可采购 ⇒ 做原型不必自研射频。

## 必须修正的两点
1. **不能主张"第一次用毫米波做隐私友好交互"** ✗ —— 已被 mmHRI 占了。
   硬写会被当场问倒，正是导师说的"有些问题别人已经解决了"。
2. **把 mmHRI 从"竞争者"改用作"可行性背书"** ✓ —— 它证明这条路线成立
   （穿透遮挡、无需影像、精度可用）。我们因此不必自证"毫米波能不能用"，
   可以直接引用它，专注我们自己的问题。

## 收窄后的主张（场景不同 ⇒ 问题不同）
mmHRI = 公共场所的机器人操纵（**做事**，指标是识别率/任务成功率）；
我们 = 居家长期陪伴（**相处**，指标是关系感知、打扰容忍度、长期可用性；
感知对象是久坐场景的微小活动、在场/离席、作息节律）。
⇒ 研究问题可写成：「当陪伴智能体能感知"你在不在、在做什么"、且不依赖摄像头时，
   用户对它的关系感知与打扰容忍度如何变化？」

## 仍未查（不许写成"据我们所知没人做过"）
是否已有人把毫米波用于**居家/情感陪伴**场景 —— 本次只查到机器人操纵与智能环境手势；
写"据我们所知还没有人……"之前必须再做一轮针对性检索（关键词已列在文档里）。
另：外部装置的输出格式与参数，需确认后才能写进方案。
"""
p = os.path.join(MAP, "_msg_mmwave.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
