# -*- coding: utf-8 -*-
"""提交检查项修正，并如实记录三个**仍未解决的开放问题**。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """test(accept): 检查项跟上今天的改动；并如实暴露三个开放问题（不掩盖）

一、修正的检查项（都是"检查器过时"，不是 App 缺陷）
  ②c 手部试手：进 AR 页前先写 files/vrm_fake_period.txt（试手周期），并把判定细分：
      判定未启动 ⇒ SKIP；启动了却没命中 ⇒ FAIL（附日志行）。
  ④ 返回键：改成**新语义**。今天为防底部误触加了"页面切换即清零退出计时"，
      正确行为变成"在首页连按两次（2 秒内）才退出"，旧检查项仍按"按两次就退出"判，属于过时。
  ⑥ 识别自检：设置页可滚动，而今天新加的「离线识别（实验）」把下面几行推下去了
      ⇒ 找不到就先向下滑几次再找（此前直接判 SKIP）。

二、**仍然 FAIL 的三个开放问题（如实列出，等下一步排查）**
  ②c 手部试手：vrm_ar.log 只有「手部判定启动：视口=1224x2358 fov=34.0 假手周期=4000ms」，
      **没有一次「手部命中」**。即：假手在跑，但从未与命中区相交 ⇒ 设备侧的手部命中链路可疑
     （JVM 单测里 HandTracker/HandTouch 全绿，所以问题在真机集成这一层）。
  ④ 返回键：tapping 首页后连按两次返回，**前台仍是本应用**（期望第二次后退出）。
     与编写的语义不符 ⇒ 需要再打点确认第二次 BACK 到底被谁消费了。
  ⑤b 离线 TTS：[tts] main：准备构造；isMain=true 之后没有任何成功/失败行 ⇒ 离线合成没走完
     （App 没崩，属静默失败；与之前离线识别原生库崩溃是同一类"原生这一层不可靠"的问题）。

三、本轮通过的部分（18 项 PASS，含关键的两条）
  ⑩1 **3D 页真的画出来了**：中段区域不同颜色数 = 25287（阈值 200）⇒ 像素级客观证据。
  ②b 音量键拍照：shoot → 已保存到相册 Pictures/AIpet/AIpet_20261011_212132.png ✓
  ⑨3 聊天页不再闪退：pid 8722→8722，前台仍是本应用 ✓
"""
p = os.path.join(MAP, "_msg_checkers.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
