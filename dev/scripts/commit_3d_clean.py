# -*- coding: utf-8 -*-
"""提交：3D/AR 画面清理（调试文字只进日志）+ 3D AR 验证结论。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """fix(3d): 调试信息只进日志、不再画到页面上；并确认 3D AR 叠加已真正可用

一、画面清理
  note() 之前会把调试文字写进 position:fixed 的 #err 层 ⇒ 3D/AR 画面上盖了一层字，
  既影响观感，又让人误以为"模型没出来"。现在 note() **只改标题**（Kotlin 侧把标题变化
  记进 vrm.log），画面上不再出现任何调试文字。

二、3D AR 实测（真机 MIS-AL00 / Android 12，以**截图**为准）
  · 相机实时画面 + 透明 VRM 叠加**已经正常工作**：白 T 恤/黑短裤/球鞋的模型
    脚踩在真实地面上，控件齐全（返回/干净/试手/VRM_OK/拍照/已拍 0）。
  · 相机 FOV 同步链路确认有效：从 Camera2 互操作读到"传感器 8.19x6.14mm、焦距 5.75mm
    → 竖直 FOV 70.9°"并调用 __setFov 推给页面（日志为证）。
  · 画面里"她只剩身体、头被切掉"不是 bug：当时手机是**朝下**拿的（俯角把地面拉进画面），
    三维透视正确；把手机端平即可看到全身，AR 页也支持双指缩放/拖动微调。
  · 页面里 place 那行日志里显示的 fov=34 是**加载时**的初值，真实 FOV 随后才同步，
    所以别用它判断取景。

三、验证方式的变化（这条最重要）
  此前我用日志里的 VRM_OK 当成"3D 成功了"，被用户指出"我从始至终没看见任何模型"——
  日志只是日志，**屏幕才是事实**。从现在起 3D/AR 的结论一律以**截图**为准：
  本轮两张截图分别是"3D 演示页（正面微笑、画面干净）"与"3D AR（站在真实地面上）"。
"""
p = os.path.join(MAP, "_msg_3d_clean.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 3D/AR 画面清理与验证脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
