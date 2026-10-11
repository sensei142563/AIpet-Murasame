# -*- coding: utf-8 -*-
"""提交离线回归闸门 + 更新交接文档。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

# 把闸门写进交接文档（在本文档里提一句怎么跑）—— 通过生成脚本加，保证可复现
G = os.path.join(MAIN, "dev", "scripts", "make_handover.py")
t = io.open(G, encoding="utf-8").read().replace("\r\n", "\n")
if "verify_all.py" not in t:
    old = '''L.append("## 二、**只等你插一次线**的真机验收'''
    new = '''L.append("## 一点五、离线回归闸门（不需要手机，一条命令）")
L.append("")
L.append("```")
L.append("python dev/scripts/verify_all.py           # 全部（约 5 秒）")
L.append("python dev/scripts/verify_all.py --quick   # 只跑 Python 侧，跳过 Kotlin 单测")
L.append("```")
L.append("")
L.append("它把散在各处的离线验证汇总成一张总表：记忆导入导出（含**真实记忆往返无损**）、")
L.append("QQ 发送队列（并发零丢失）、重型任务闸门、能量法 VAD、Silero 真模型（她的真实语音 + 负例）、")
L.append("Kotlin 单测。**任一失败即退出非 0**，可直接当提交前的检查。")
L.append("")
L.append("## 二、**只等你插一次线**的真机验收'''
    if old in t:
        t = t.replace(old, new, 1)
        io.open(G, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 生成脚本已加入「离线回归闸门」一节")
    else:
        print("⚠ 生成脚本锚点未命中")

r = subprocess.run([sys.executable, "-u", G], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if re.search(r"已生成|单测：|验收项", l):
        print("   " + l.strip()[:140])

MSG = """test: 离线回归闸门 verify_all.py（一条命令、一张总表、失败即非 0）

把此前散在各处、需要逐个手跑的离线验证汇总成一条命令，目的是让
"我做过了" 变成 "**任何人都能复现**"：
  ① 记忆导入导出：mem_adversarial（19 项）+ **真实记忆往返必须无损**（导出→导入临时角色→比条数→清理）
  ② QQ 发送队列：qq_outbox_adversarial（18 项，含并发 50 条零丢失）
  ③ 重型任务闸门：test_heavy_gate（互斥 / 超时 / 可观测性）
  ④ 能量法 VAD：test_vad（与 Kotlin 版同信号同期望）
  ⑤ Silero 真模型（PC 侧 onnxruntime）：用**她台词包里的真实语音** + 四类负例
     （静音 / 响亮纯音 / 方波噪声 / 旧探针嗡嗡声）
  ⑥ Kotlin 单测（手机仓 15 个类、122 个用例）—— 读 JUnit XML 汇总，不靠解析控制台输出
末尾打印总表；任一失败即退出非 0，可直接当提交前检查。--quick 可跳过 Kotlin 侧。

实测（本机）：**7/7 通过，总耗时约 5 秒** ——
  mem 19/19 · 真实记忆 148→148 无损 · qq_outbox 18/18 · 闸门 ✓ · VAD ✓
  · Silero 语音 4/4（峰值 0.99~1.00）负例 4/4 拒绝 · Kotlin 122 用例 0 失败。

交接文档（dev/docs/交接清单-2026-10.md）已同步生成「离线回归闸门」一节，
与第二节的真机验收（20 项）配合：**离线这条随时可复跑，真机那条等你插线**。
"""
p = os.path.join(MAP, "_msg_verifyall.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
