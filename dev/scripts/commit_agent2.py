# -*- coding: utf-8 -*-
"""跑全量并提交：修正嵌套函数缩进错误 + available() 包 try。"""
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

MSG = """fix(agent): 修正我上一轮把两个方法插成"嵌套函数"的缩进错误 + 探测失败不再带走整只桌宠

一、**我自己的错误**（如实记录）
  上一轮恢复「agent 任务」链时，我把 `_run_agent_task` / `_on_agent_done` 插成了 **8 空格缩进**，
  而类方法应该是 **4 空格** —— 给"已经带 4 空格的行"又加了一层。
  后果：它们变成了**嵌套函数**而不是类方法 ⇒ `pet._run_agent_task` 根本不存在
  ⇒ test_qt_lifecycle 的 A2 段在 `SECOND_RETURNED` 那一步就断掉，后续 6 项全部"没打印"。
  ⚠ **教训（很值钱）**：这类错误 **py_compile 抓不到**（嵌套 def 本身是合法语法），
     必须用 `hasattr(Class, "method")` 这类**语义检查**才能发现。
     本轮已经在验证脚本里加上了这一步：`IS_METHOD True`。
  修法：把这两个方法整体退回 4 空格。

二、顺手修的产品侧真问题：`available()` 探测失败会带走整只桌宠
  `tool/agent_bridge.py::available()` 会去找 node / DSH 的 bin.js / Codex 的 bin/codex.js，
  **可能抛异常**；而 `_run_agent_task` 里 `av = available()` **没有包 try** ⇒
  一次"探测失败"就把异常冒到调用方，整只桌宠被打断。
  改为 try/except：探测失败按"没有可用的 agent"处理，如实说一句就返回 True，绝不上抛。

验证：
  · `tests/test_qt_lifecycle.py` → **全部通过，退出码 0**（修前 23 OK / 7 FAIL，其中 1 项是启动路径）。
    关键证据：SECOND_RETURNED **True**、STOPPED_IN **0.31** 秒、TMPMEM_FILES 2、
    "收尾后外部 agent 进程也没了"、"没有 QThread 告警/abort" 全部 OK。
  · 语义检查：`hasattr(Murasame, "_run_agent_task") and hasattr(Murasame, "_on_agent_done")` → True。
"""
p = os.path.join(MAP, "_msg_agent2.txt")
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
