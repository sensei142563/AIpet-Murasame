# -*- coding: utf-8 -*-
"""把记忆互通真机往返接进 accept_all.py（第 ⑪ 节，调用独立脚本），然后提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
MAP = os.path.join(MAIN, "dev", "merge-map")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "⑪ 记忆互通真机往返" in t:
    print("· 已有 ⑪ 节")
else:
    block = '''    # ===== ⑪ 记忆互通真机往返（用户原目标的第一条）=====
    print("=== 7. 记忆互通（真机往返）===")
    if DRY:
        record("⑪ 记忆互通真机往返", "SKIP", "dry-run")
    else:
        rt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mem_device_roundtrip.py")
        if not os.path.isfile(rt):
            record("⑪ 记忆互通真机往返", "SKIP", "缺少 mem_device_roundtrip.py")
        else:
            rr = subprocess.run([sys.executable, "-u", rt], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800,
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            oo = (rr.stdout or "") + (rr.stderr or "")
            lines = [l.strip() for l in oo.splitlines() if "PASS" in l or "FAIL" in l]
            detail = "；".join(l[:60] for l in lines[:4]) or "(无输出)"
            record("⑪ 记忆互通真机往返", verdict(rr.returncode == 0), detail)

'''
    anchor = '''    print()
    print("=== 汇总 ===")'''
    if anchor in t:
        t = t.replace(anchor, block + anchor, 1)
        io.open(A, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已插入第 ⑪ 节（调用独立脚本）")
    else:
        print("✗ 汇总锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
if r.returncode != 0:
    sys.exit(1)

MSG = """feat(memory): 记忆互通真机往返验证（双向无损 + 合并幂等），并接进验收

用户原目标的第一条是「④ 记忆互通（导出/导入先行）」。此前只验过离线 CLI 往返
（verify_all.py 里 148→148），**真机这条链一次没走过**。现在补上，而且不需要人工点界面 ——
App 冷启动时本来就会：① 先合并 memory_io/import/ 下的文件；② 再写快照到 memory_io/export/。

新增 dev/scripts/mem_device_roundtrip.py（一条命令跑完 5 项）：
  ① 手机侧有导出包            —— 从 memory_io/export/ 拉最新包
  ② 手机 → 桌面 无损          —— 桌面导入临时角色，条数必须等于手机包的条数
  ③ 桌面包推入手机 import/    —— 桌面导出后 push 进手机等待导入目录
  ④ 桌面 → 手机 合并生效      —— 冷启动 App（自动合并）→ 拉新快照 → 条数 ≥ 两边最大值
  ⑤ 重复冷启动不膨胀（幂等）  —— 再冷启动一次，条数不应增长

真机实测（MIS-AL00 / Android 12）**5/5 通过**：
  ① 手机包 299 条（80717 字节）
  ② 手机包 299 条 → 桌面 299 条（短 251 + 长 48，新增 0 重复 0 跳过）⇒ **完全无损**
  ③ 桌面 172 条已推入手机 import/
  ④ 冷启动合并后 299 条（≥ max(299, 172)）
  ⑤ 第二次冷启动仍是 299 条 ⇒ **合并幂等**（不丢、不重复膨胀）
  交叉印证：桌面 172 条里只有 24 条是手机没有的 ⇒ 148 条共有，
  与离线分析得出的"148 条共有记录"完全吻合。

顺手修了我自己的一处计数错：第一版只数了 history.json（251），没加 long_history.json（48），
把"完全无损"误判成 FAIL —— 桌面侧条数必须是**短 + 长**之和。

同时把这一节接进 accept_all.py（第 ⑪ 节，调用独立脚本），以后每次验收都会自动验一遍。
"""
p = os.path.join(MAP, "_msg_mem_rt.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
