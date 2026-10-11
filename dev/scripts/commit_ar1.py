# -*- coding: utf-8 -*-
"""提交地板/碰撞箱几何件 + 单测。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"

MSG = """feat(ar): 地板识别 + 碰撞箱的几何件（纯计算 + 10 个单元测试，全部离线可验）

目标里"类似 OCR、识别地板等等的碰撞箱、动捕、手部和 AR3D 任务互动"这条线，
第一步先把**几何基础**做扎实：手机 AR 是 CameraX + Live2D/GL 叠加，引入 ARCore 要换整条
渲染与生命周期通路，所以先用**姿态法**拿到"地面在哪"，并且把这部分做成**无 Android 依赖的
纯计算件**，于是可以完全离线用 JVM 单测证明它对。

新增 app/src/main/java/com/aipet/murasame/ui/ArGround.kt：
  · pitchDeg(gx,gy,gz)      加速度计 → 俯仰角（光轴与水平面夹角，下俯为正）
  · focalPx(viewportH,fov)  由竖直 FOV 得焦距像素
  · horizonY(...)           地平线在屏幕的 y（下俯越大越靠上）
  · groundPointY(...)       地面上某距离的点投影到屏幕的 y（= 脚该踩的位置）
  · charPixelHeight(...)    某距离上"身高 charHeightM"该占多少像素（透视缩放）
  · collisionRect(...) / hit(...)  屏幕空间碰撞盒与命中判定（戳她一下的手部互动基础）
  · horizonVisible / groundCoverage  当前能不能看到地面、地面占画面比例
  · describe(...)           一行调试摘要
  坐标系约定写在文件头（pitch=0 光轴水平、>0 下俯；屏幕 y 向下为正）。

新增 app/src/test/java/com/aipet/murasame/ArGroundTest.kt（10 个用例）：
  实测结论（gradlew :app:testDebugUnitTest → ArGroundTest tests=10 failures=0，
  连同既有 NativeSmokeTest 4 个，共 **14/14 全绿**，不需要手机）：
   · 光轴水平时地平线正好在画面中心（y=h/2）✓
   · 下俯 15° → 地平线 y 从 1000 升到 536（60° 竖直 FOV、2000px 高）✓
   · **下俯 30° 时地平线已跑出画面顶**（理论值 0）→ 地面覆盖率达到 1.0 ✓
     ⇒ 实用结论：低头二十几度就"看到满地"，不需要低很多头
   · 相机高 1.5m、下俯 20° 时，2m 处的脚点在 1330px、5m 处在 1153px（越远越接近地平线）✓
   · 身高 1.5m、距离 2m、60° FOV、2000px → 角色高约 **1299px**（近大远小，4m 处减半）✓
   · 焦距：60° FOV/2000px → f≈1732px；FOV 变窄焦距变长 ✓
   · 碰撞盒：底边=脚、顶边=头顶；盒心/头部命中，脚下与盒外不命中 ✓
   · 加速度计映射：竖直=0°、平放朝下=90°、45° 斜看=45°（±0.6°）✓

单测暴露并修掉的一个健壮性问题：`horizonVisible` 原本用严格 `y > 0`，
而 60° FOV 下俯 30° 的**理论值正好是 0**，浮点算出极小正数 → 在刀刃角度上答案不稳定；
现在用 1px 容差（也写进了注释）。

能力边界（诚实标注）：这是**单目 + 姿态估计**，能给出地平线/地面区域/脚位/透视缩放/碰撞盒，
**不能**给出真实距离与遮挡 —— 那需要 ARCore 深度或多帧 SLAM。

顺带说明「类似 OCR」：本 App 已有识图链路（VisionClient → 配置里的视觉模型，默认 qwen3-vl-plus），
拍照识字/识物走它即可，本轮不重复造。
"""
p = os.path.join(MAP, "_msg_ar1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
