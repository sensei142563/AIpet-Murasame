# -*- coding: utf-8 -*-
"""跑全量并提交 vision 判据更新。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

MSG = """fix(vision): 判据按拍板改判 —— 本地视觉「仅保留接口」；test_vision_interface 全绿

用户 2026-10-13 拍板：**本地视觉不使用，仅保留接口**。
于是把测试里"按上游语义写的"那批检查**反过来**，改判为校验已拍板的设计。

一、tests/test_vision_interface.py
  · 文件头补一段说明：本文件只校验"接口本身还在、行为可预期"，
    不再要求接上上游那套 UI 面（那是否决的设计）。
  · 第 2 节由「示例配置必须有 vision_source / vision_local_url / vision_local_command /
    vision_local_model」+「设置页必须有来源选择器与两个输入框」
    → 改判为「示例配置里**没有**这四个键」「设置页**没有**那套控件」，
      同时保留「V.SOURCES 仍是 (cloud, local)」这条（证明**接口没被删**）。
  · 第 5 节由「摄像头识图必须按 vision_local.source() 分支」
    → 改判为「摄像头识图**不**走 vision_local 分支」+「也没有活的 `from tool import vision_local`」，
      并保留「云端没配模型时不再静默」这条有价值的不静默检查。
  · 第 1/3/4 节**原样保留**（默认 cloud、HTTP 认四种响应形状、CLI 允许带参数、
    错误提示可读）—— 这些正是"接口保留"的证据。

二、config.example.json：删掉 `vision_source: "local"`
  它是唯一的"上游专用"键（另外三个本来就不在）。值是 **local** ⇒ 等于**默认走本地视觉**，
  与拍板相反，删。删后示例里保留的 vision* 键都是**我们在用的**：
  vision_local_model_dir / vision_local_port / vision_max_side / vision_model_name /
  qq_vision_enabled / vision_idle_unload / vision_fast_max_side / vision_threads / vision_max_new。

验证：`tests/test_vision_interface.py` → **本地视觉接口体检全部通过，退出码 0**（修前 17 OK / 9 FAIL）。
"""
p = os.path.join(MAP, "_msg_vision.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
