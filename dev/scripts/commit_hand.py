# -*- coding: utf-8 -*-
"""提交 ②c 的结论与可观测性改进，然后启动完整验收。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """test(hand): 手部命中链路真机验证通过（40 秒 4 次，正好一次扫描一次）+ 坐标可观测

一、结论：**链路是通的**，之前验收报 FAIL 属于检查时机/触发器问题
  按下「试手」后（假手周期 4 秒），vrm_ar.log 稳定出现：
      手部命中 BODY（假手=true 周期=4000ms 视口=1224x2506 fov=70.9 pitch=1.11）
        ↳ 摸到身子
  40 秒内 4 次命中 ⇒ 恰好一次扫描命中一次，符合设计（HandTouch.Latch 3 帧确认 + 12 帧冷却）。
  整条链路"关键点 → 屏幕坐标 → 碰撞盒 → 通知页面做反应"在真机上打通。

二、一次**自我纠错**（如实记录）
  我一度判断"假手坐标系是视图系 ⇒ rotationDeg 必须为 0，默认 90 导致永不命中"，
  并据此改了代码。真机复测打脸：日志显示 `rotation=90` 时**命中照样成立**，
  而且那个 if 分支在启动时根本不生效（fake 是点「试手」之后才置位的）。
  ⇒ 已**撤掉该改动**（不去修没坏的东西），只保留可观测性。

三、保留的可观测性（本次新增）
  · 启动日志补上 rotation / mirrored 两个值，避免以后再靠猜。
  · 每秒一行坐标对比：
        手部坐标 帧=(815,1644)/1224x2506 rot=90 → 屏幕=(-189,1669) | 碰撞盒=234,1105,990,2479 视口=1224x2506
    （碰撞盒最初打印成 FloatArray 的身份 [F@a3be4b2，看不懂；已改为 4 个数值。）
    有了这行，下次"命中/不命中"都能直接看数字，不用猜坐标系。
"""
p = os.path.join(MAP, "_msg_hand.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 手部命中验证与坐标埋点"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
