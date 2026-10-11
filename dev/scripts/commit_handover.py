# -*- coding: utf-8 -*-
"""核对交接文档后段 + 提交（文档与生成脚本）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")
DOC = os.path.join(MAIN, "dev", "docs", "交接清单-2026-10.md")

txt = io.open(DOC, encoding="utf-8").read()
lines = txt.split("\n")
print("=== 文档结构（所有标题）===")
for i, l in enumerate(lines, 1):
    if l.startswith("#"):
        print("   %4d| %s" % (i, l[:120]))

print()
print("=== 第四节（未验证项）全文 ===")
i = txt.find("## 四、")
j = txt.find("## 五、")
print(txt[i:j] if i > 0 and j > i else "(未找到)")

print()
print("=== 第二节的检查项清单 ===")
i = txt.find("覆盖的检查项：")
j = txt.find("**三处")
print(txt[i:j] if i > 0 and j > i else "(未找到)")

print()
print("=== 提交 ===")
MSG = """docs: 交接清单（从真实状态自动生成，含未验证项的诚实清单）

按上一轮的建议停止新增功能，改为把已有成果固化成可交接的文档：
dev/docs/交接清单-2026-10.md，由 dev/scripts/make_handover.py **从真实状态生成** ——
  · 单测数量与类名：读 app/build/test-results 下的 JUnit XML（当前 122 个用例 / 15 个类）；
  · 真机验收项：解析 dev/scripts/accept_all.py 里的 record("…") 名字；
  · 提交数与工作区状态：git rev-list / git status；
  · 未验证项：从最近 60 条提交信息里检索「未验 / 需上机 / 无法在 JVM 单测」等字样。

文档内容：
  一、当前状态硬数字（两仓未推送数、单测数、最新提交）；
  二、只等你插一次线的真机验收（一条命令 + 15 个检查项 + 三处"当场可修旋钮"的对照表）；
  三、需要你出手的两件事（手机端装 NapCat、用 VRoid 做她的 VRM，含验证命令）；
  四、已知未验证项（提交里检索到的 + 从设计上无法在 JVM 单测覆盖的，如 Keystore 加解密、
      压缩资产取长度分支、Silero 真机阈值、onGiveUp 是否接上、NapCat 重投行为）；
  五、我给出的建议（停止离线扩面，转入真机验收与按诊断包逐项修）。

重新生成：python dev/scripts/make_handover.py（数字会刷新，不需要手改）。
"""
p = os.path.join(MAP, "_msg_handover.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
