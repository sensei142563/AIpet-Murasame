# -*- coding: utf-8 -*-
"""① 把 MMEdge / HALO 作为技术依据补进规划文档的「3. 第三块：未来规划」
   （只用公开论文信息；不含任何未发表内容与个人指向）
   ② 推送电脑端仓库
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
DOC = os.path.join(ROOT, "dev", "docs", "汇报PPT规划-2026-10-13.md")

print("=== ① 先看现状：§3 与 §4 ===")
t = io.open(DOC, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
m3 = t.find("## 3. 第三块：未来规划")
m4 = t.find("## 4. 制作顺序")
print("   §3 起于 %s，§4 起于 %s" % (m3, m4))
if m3 >= 0 and m4 > m3:
    for l in t[m3:m4].split("\n"):
        print("   | " + l.rstrip()[:108])

ADD = """
### 3.x 技术依据（新增 · 2026-10-14 · 全部为**公开论文**）

> 以下是老师转发来的三篇里的两篇，**只作技术路线依据**；落地与否另行决定。

**① MMEdge — 边缘设备上的实时多模态推理（HKUST）**
- 论文：*MMEdge: Accelerating On-device Multimodal Inference via Pipelined Sensing and Encoding*
- 关键做法：把推理拆成**细粒度「感知 + 编码」单元**，数据一到就增量计算（**不等完整输入**）；
  另有**跨模态推测跳过**（某模态提前高置信就跳过慢模态的后续单元）与**自适应配置优化器**
  （延迟约束下动态选感知/模型配置）。
- 对我们的用处（**手机端**）：现在「相机帧 → 关键点 → 命中她 → 反应」是**整帧串行**；
  可照它做**流水线 + 跳帧 + 早停**，并把"相机参数"纳入"延迟约束下选配置"的框架。
  ⇒ 与「近期：手机端真机验证与调优」直接对应。

**② HALO — 异构感知的语言对齐基础模型（HKUST，与 MMEdge 同一课题组）**
- 论文：*HALO: A Heterogeneity-Aware Language-Aligned IMU Foundation Model for Open-Set HAR*
- 关键做法：面向 IMU（加速度计/陀螺仪）做**跨设备、跨采样率、跨佩戴位置**的统一编码
  （heterogeneity-aware tokenization + 语言对齐 + 开放集），**可训练参数仅约 35M**
  （对照 MOMENT 341.2M，少 10×）。
- 对我们的用处（**非视觉感知路线**）：PPT 里写的是"传感器输出**标准化参数流**"；
  HALO 解决的恰是"不同设备/不同采样率如何统一"这一问题，且 35M 量级**手机端可跑**。
  ⇒ 将来接非视觉感知时，**不要为每种设备写一套**，而是做一层「语言对齐 + 异构适配」的统一编码器。

**③ 另一篇（仅存档，不进入路线）**：*OphVLM-R1*（眼科推理 + 课程式 RL，2B 超过 4B 对照）——
领域无关，但"**小模型靠训练策略打赢大模型**"这一结论可作规划时的旁证。

> ⚠ 记录纪律：以上均引自**公开论文**；与外部装置有关的未发表工作**不得写入本文档或代码**。
"""
if "MMEdge" not in t:
    if m4 > 0:
        t = t[:m4] + ADD.strip() + "\n\n" + t[m4:]
    else:
        t = t.rstrip() + "\n\n" + ADD
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(t)
    print()
    print("   ✓ 已补入 3.x 技术依据（插在 §4 之前）")
else:
    print()
    print("   · 已存在，跳过")

print()
print("=== ② 提交并推送 ===")
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
MSG = """docs(plan): 规划文档补入 MMEdge / HALO 作为技术依据（公开论文）

## 来源
老师转发的三篇里的两篇（均为公开论文）：
- MMEdge: Accelerating On-device Multimodal Inference via Pipelined Sensing and Encoding (HKUST)
- HALO: A Heterogeneity-Aware Language-Aligned IMU Foundation Model for Open-Set HAR (HKUST)

## 补进规划文档的什么
`dev/docs/汇报PPT规划-2026-10-13.md` §3「未来规划」下新增 **3.x 技术依据**：
- **MMEdge → 手机端**：把「相机帧 → 关键点 → 命中 → 反应」从整帧串行改成
  **流水线 + 跳帧 + 早停**，并把相机参数纳入"延迟约束下选配置"的框架；
- **HALO → 非视觉感知路线**：我们写的是"标准化参数流"，它解决的正是"不同设备/采样率如何统一"，
  且 ~35M 可训练参数（对照 MOMENT 341.2M）⇒ 手机端可跑；将来**别为每种设备写一套**，
  做一层"语言对齐 + 异构适配"的统一编码器；
- 第三篇（OphVLM-R1）只作旁证：小模型靠训练策略打赢大模型。

## 纪律
只引用**公开论文**；与外部装置相关的未发表工作**不写入文档或代码**（本条也已写入文档作为记录纪律）。

## 同时修正的 PPT 断言
主人质疑「手机端 3D 模型怎么与人交互？我没发现」。核实结果（依据 chatter 仓
`docs/手部互动-实现与验证状态.md` 与 `VrmArScreen.kt` 注释）：
- 代码链路是**完整**的：CameraX → HandDetector(MediaPipe 21 关键点) → HandTracker →
  VrmArScreen 15Hz → `evaluateJavascript` → `assets/vrm/index.html` 的
  `__poke/__pinch/__wave/__lookAt`；
- 但**真机从未用真手验过**（文档原话"真机：完全没验过"）；真机只跑过**假手**的坐标链路
  （rotation=90，40 秒命中 4 次）；且 VRM 模型需 `adb push` 到 `files/vrm/model.vrm`；
- 所以 PPT 第 21 页措辞已改为准确版：标题"（代码链路已通，真机待验）"、
  三条"代码已通"、"未验证：真机（从未用真手验过）"，并写明"要用真手须先关掉「试手」、
  并先 push .vrm 模型"。**图片位置尺寸经断言完全未变（15/15）。**
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_plan.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
r = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("   ✓ 提交：%s" % (r.stdout or r.stderr or "").splitlines()[0][:140])

br = subprocess.run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
up = subprocess.run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "@{u}"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   当前分支 %s；上游 %s" % (br, (up.stdout or "").strip() or "（无）"))
cmd = ["git", "-C", ROOT, "push"]
if not (up.stdout or "").strip():
    cmd += ["-u", "origin", br]
print("   执行：" + " ".join(cmd[3:] if len(cmd) > 3 else cmd[3:]))
r2 = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=1800)
out = ((r2.stdout or "") + (r2.stderr or "")).strip()
for l in out.split("\n")[-12:]:
    if l.strip():
        print("      " + l.strip()[:130])
print("   推送退出码 = %d" % r2.returncode)
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "@{u}..HEAD"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace").stdout.strip()
print("   推送后仍未推送：%s 条" % (n or "?"))
