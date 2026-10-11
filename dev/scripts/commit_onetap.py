# -*- coding: utf-8 -*-
"""提交一键填入，并输出当前累计条数（用于汇报）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """feat(net): 找到电脑后一键填入两处地址（热点链接闭环）

扫描到电脑（api.py 28565 有响应）后，直接把两处地址写好，用户不用再手填：
  · 语音服务地址（电脑 F5-TTS）  → http://<电脑IP>:9881
  · Jev 电脑地址（api.py）        → http://<电脑IP>:28565
并在那一行如实显示填了什么（"找到电脑：x ⇒ 已自动填入 语音 … 与 Jev …"），
用户看得见、也能随时改。

这样"热点链接"的完整流程就是一句话：
  手机开热点 → 电脑连热点 → App 里点「网络自检（找电脑）」→ 地址自动填好，直接能用。
"""
p = os.path.join(MAP, "_msg_onetap.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 一键填入地址的脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
print()
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净" if not st else "%d 项" % len(st.splitlines())))
