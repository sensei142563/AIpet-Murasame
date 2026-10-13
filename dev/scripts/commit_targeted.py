# -*- coding: utf-8 -*-
"""补记"针对性检索"的结果：确认"居家/情感陪伴 + 非摄像头感知"这条**已有相邻工作**，
   所以我们连"据我们所知还没人做过"这句话也**不能写**；
   只能把主张收到"问题框定（陪伴 vs 操纵）与指标（关系、打扰）"这一层。
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

### 补记：针对性检索做完了 —— 连"据我们所知还没人做过"也不能写

上一节留了一条"必须再做一轮针对性检索"。做了，结果是：**相邻工作确实存在**。

| 找到的东西 | 与我们的关系 |
|---|---|
| 《Bridging Functional Computing and Emotional Companionship: An **AIoT**-Based Computational Framework for Evaluating **Smart Home Care**…》（ACM，DOI 10.1145/3804504.3804536） | **"传感器 + 居家照护 + 情感陪伴 + 评估框架"** 这件事已经有人在做 ⇒ 我们不能说这个组合没人碰过（全文页被 Cloudflare 挡住，只核到标题与出处，**细节未读，不作引用**） |
| ATTENTION NoOKs（UChicago axlab）："our implementation … relies on simple **presence detection**" | "用在场检测来决定要不要打扰" 已有实现 ⇒ 我们"打扰边界"的想法不是全新 |
| Will: AI robot cat（Kickstarter，edge AI 情感陪伴机器猫）；Roomba 发明人的 AI robot pet | 情感陪伴型硬件已是**在售/众筹产品** ⇒ "情感陪伴 + 具身"不是空白 |
| Dogu 等（TechRxiv，Queen Mary 天线/mmWave 组） | 毫米波感知在健康/居家方向的相邻工作（**细节未读，不作引用**） |

⇒ **结论（按纪律，只能这么写）**：
1. **不能写**"我们第一次把非摄像头感知用于陪伴" ✗
2. **不能写**"据我们所知还没有人做过" ✗
3. **可以写**的是**问题框定的差异**：
   - 他们把**感知/照护/在场**当目标（指标是识别率、照护效果）；
   - 办公线把**任务**当目标（指标是效率、留存）；
   - **我们把"角色的人格连续性"当变量**，研究它对**关系感知与打扰容忍度**的影响 ——
     这一层在本次检索里**没有见到对应的工作**（但"没见到"≠"不存在"，
     正式写作时应当以"我们关注的问题是……"起句，而不是"据我们所知没人……"）。
4. 任何引用上述文献时，**只引标题与出处，不引没读到的结论**。

> 附：这条纪律本身就是 PPT 的加分项。导师原话里最重的一句是"1. 有些问题别人已经解决了"，
> 而我们能拿出"我们查过、这里已经有人做了、所以我们把主张收到这一层"的过程，
> 比任何漂亮话都更能证明**我们在认真做调研**。
"""

t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "针对性检索做完了" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 已补记针对性检索结果")
else:
    print("· 已有该节")

MSG = """docs(research): 针对性检索补完 —— 相邻工作存在，主张只能收到"问题框定"这一层

上一节留了"必须再做一轮针对性检索"，做完了，结果**又是收紧而不是放宽**：
· ACM《Bridging Functional Computing and Emotional Companionship: An AIoT-Based
  Computational Framework for Evaluating Smart Home Care…》(10.1145/3804504.3804536)
  ⇒ "传感器 + 居家照护 + 情感陪伴 + 评估框架"这个组合已有人做
  （全文被 Cloudflare 挡住，只核到标题与出处，**细节未读、不作引用**）；
· ATTENTION NoOKs（UChicago axlab）明确写着用 simple presence detection
  ⇒ "用在场检测决定是否打扰"已有实现；
· Will（Kickstarter 的 edge AI 情感陪伴机器猫）、Roomba 发明人的 AI robot pet
  ⇒ 情感陪伴型硬件已是在售/众筹产品；
· Dogu 等（TechRxiv，Queen Mary 天线/mmWave 组）⇒ 毫米波居家/健康方向的相邻工作
  （细节未读，不作引用）。

结论（按纪律只能这么写）：
1. **不能写**"我们第一次把非摄像头感知用于陪伴"；
2. **不能写**"据我们所知还没有人做过"；
3. **可以写**的是问题框定的差异：他们以感知/照护/在场为目标（指标是识别率、照护效果），
   办公线以任务为目标（指标是效率、留存），**我们把"角色的人格连续性"当变量**，
   研究它对**关系感知与打扰容忍度**的影响 —— 这一层本次检索没见到对应工作，
   但正式写作要以"我们关注的问题是……"起句，而不是"据我们所知没人……"；
4. 引用上述文献只引标题与出处，**不引没读到的结论**。

附：这条纪律本身就是 PPT 的加分项——导师最重的一句是"有些问题别人已经解决了"，
而我们能拿出"查过、这里有人做了、所以把主张收到这一层"的过程，
比任何漂亮话都更能证明在认真做调研。
"""
p = os.path.join(MAP, "_msg_targeted.txt")
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
