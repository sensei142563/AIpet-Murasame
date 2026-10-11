# -*- coding: utf-8 -*-
"""提交本轮修复（手机仓）+ 桌面仓脚本。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """fix(chat): 修掉"一切到聊天页就闪退" —— 元凶是我自己加的离线识别自检

一、现象与定位（全部来自真机证据，不是推测）
  用户报告"一到聊天页就闪退"。系统侧查不到任何崩溃痕迹：
    · crash buffer 空、dropbox 无 tombstone、events 里没有 am_crash
    · 只有 am_proc_died，且 appDiedLocked **fromBinderDied=true**
    · 我们自己的 onPause/onDestroy 都没执行 ⇒ 根本没走到 Java 层
  于是给 App 补观测能力（新建 Diag.kt）：全局未捕获异常处理器、Activity 生命周期
  （onDestroy 连调用栈一起写）、tab 点击、聊天页组合，全部写 external files/diag.log。
  装上后一次复现就抓到，diag.log 最后一条是：
      [Chat] ASR 自测 开始（原生模型初始化）
  之后什么都没有 —— 就是 OnlineAsr.selfTest()（加载 SenseVoice 原生模型）执行时
  让原生层崩掉、进程被内核收走。这段"识别自检"是我早先为验证 STT 加在聊天页组合里的
  诊断代码，不该在进入页面时跑。这是我的锅。

二、修复
  ① 从聊天页组合里移除 ASR 自检调用（需要自检时在设置页手动点）。
  ② OnlineAsr 增加总开关 offlineEnabled(ctx)：**默认停用**，停用时 init()/selfTest()
     根本不加载原生库。理由：该原生库在这台机器上"初始化即崩"，而它是不可恢复的
     进程级崩溃，不能用 runCatching 兜。要在本机实验时，创建
     files/asr_offline_enabled.txt 内容写 1 即开启。
  ③ 长按说话的语音输入：离线识别停用时自动改用**系统识别**（RecognizerIntent），
     不再触碰原生库；系统识别也没有时给出明确提示。

三、顺带修的两处用户反馈
  ④ 记忆页「整包备份/导出互通包/导入互通包」原来塞在 SectionCard 的 trailing 槽里，
     那块地方窄，中文放不下被逐字折行 ⇒ 显示成竖排。改为放在内容区、三个按钮
     weight(1f) 等宽平分、字号 13sp、maxLines=1。
  ⑤ 首页 QQ 卡文案：「打开 QQ 通道」含义不清 ⇒ 改为「打开 QQ 面板」，并在卡上写清
     两种跑法（① 电脑跑 api.py+NapCat，手机连电脑；② 手机 Termux 里自己跑 NapCat，
     用设置里的本机直连，装好后可脱离电脑）；状态行的离线提示也补上"手机本机 NapCat"。

四、验证（真机 MIS-AL00 / Android 12）
  · 装机后 lastUpdateTime 20:23:22 → 20:30:31（确认这次真的装上；上一次安装其实没生效）
  · 点「聊天」后 diag.log 走到 ChatScreen 组合完成 + 系统 TTS 引擎创建，没有 ASR 自检行
  · 进程 pid 连续存活 20 秒以上，前台一直是 com.aipet.murasame/.MainActivity（不再回桌面）

诚实标注：
  · Diag 诊断日志暂时保留（体积很小，是这次能定位问题的关键）；确认稳定后可移除。
  · 底部 tab 的点击在华为手势导航下仍有一条被系统手势区吃掉的带子（实测点 y2641 会回桌面），
    这是**另一个**独立问题，本次先用"页面切换即清零退出计时"的保险避免误退出；
    真正的布局修复（把 tab 抬出手势区）等确认后再做，避免又改坏。
"""
p = os.path.join(MAP, "_msg_chat_fix.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 聊天页闪退定位与修复脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
