# -*- coding: utf-8 -*-
"""提交设置页的离线识别开关。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """feat(settings): 离线识别做成可见开关；自检行说明停用原因

背景：离线识别（SenseVoice 原生库）在本机初始化即让 App 直接退出，所以默认停用。
但之前只能靠手写 files/asr_offline_enabled.txt 来开关，既看不见状态、也无从恢复 —— 太隐晦。

改动（聊天页 → ☰ → ⚙ 设置 里的语音区）：
  · 新增「离线识别（实验）」行：
      开启时提示「本机实测会在初始化时让 App 直接退出，谨慎使用」
      关闭时提示「已停用（推荐）—— 语音输入改走系统识别」
    点一下即切换（写/删 files/asr_offline_enabled.txt），不用再去手写文件。
  · 「识别自检」行的副标题随状态变化：停用时明确写「离线识别已停用，自检不会执行（先打开上面的开关）」，
    不再出现"点了没反应"的困惑。

真机验证（走 聊天 → ☰ → ⚙ 设置）：
    语音
      离线识别（实验） / 已停用（推荐）—— 语音输入改走系统识别
      识别自检         / 离线识别已停用，自检不会执行（先打开上面的开关）
      测试电脑语音 · 朗读 · 只回应呼唤 · 朗读音色（系统语音/离线音色）· Jev 地址 · 语音服务地址
  两行文本均已确认出现，截图见 dev/shots/settings_asr_switch.png。
"""
p = os.path.join(MAP, "_msg_asr_switch.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 设置页开关的验证脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
