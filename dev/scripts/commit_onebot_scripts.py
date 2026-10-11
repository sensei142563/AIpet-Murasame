# -*- coding: utf-8 -*-
"""提交桌面仓本轮新增的脚本与说明。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")

MSG = """chore(scripts): OneBot 解析的对抗测试脚本与读取工具

配合手机仓的 39a7744（OneBotParse 的 CQ 码映射 + 4 条"JSON null 安全性"断言）：
  · dev/scripts/onebot_adv_1.py —— 生成并运行 OneBotAdversarialTest；
  · dev/scripts/onebot_adv_fix.py / onebot_adv_fix2.py —— 本轮的两轮修复；
  · dev/scripts/read_onebotparse.py、show_bad_test_line.py —— 读源码定位用的工具。

顺带把两条经验写进注释（都来自本轮的失败）：
  1) 生成 Kotlin 的 Python 脚本里，提示语中提到字符串要用中文引号 ——
     我写了 \\"null\\"，而 Python 三引号串中 \\" 是**合法转义**，反斜杠被吃掉，
     生成出来的 Kotlin 变成裸引号导致编译失败；
  2) 测试文件由脚本生成时，直接改生成物会被下次运行覆盖，必须改脚本本身。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_onebot_scripts.txt")
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
