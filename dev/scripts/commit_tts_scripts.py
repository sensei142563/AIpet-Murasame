# -*- coding: utf-8 -*-
"""提交本轮桌面仓脚本。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")

MSG = """chore(scripts): TTS 链路审查用的探测与修复脚本

配合手机仓的 068fe86（修掉两处"静默无声" + 新增纯函数 TtsPlan 与 7 个不变量单测）：
  · probe_tts_chain.py   —— 定位 TTS 相关文件与层序；
  · read_voiceclient.py  —— 打印 VoiceClient 全文（正是靠读它看出两个真问题）；
  · find_tts_callsite.py —— 找调用点，确认 ChatScreen 里本来就有系统 TTS 兜底，
                            从而证实"异步路径 return true ⇒ 兜底永不触发"。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_tts_scripts.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
