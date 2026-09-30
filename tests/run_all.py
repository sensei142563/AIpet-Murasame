# -*- coding: utf-8 -*-
"""跑 `tests/` 下所有体检：`python tests/run_all.py [关键字]`

设计约定（都踩过坑才定下来的）：
  · 每个 `test_*.py` **可独立运行**（`python tests/test_xxx.py`），也能被这里当子进程跑 ——
    子进程隔离很重要：Qt/线程/外部进程类测试在同一个进程里会互相干扰。
  · 仓库根由 `__file__` 推出，不写死绝对路径（从任何目录都能跑）。
  · 全部用 `QT_QPA_PLATFORM=offscreen` + `AIPET_NO_SPAWN=1`：**绝不真的开窗口/拉起桌宠、QQ、微信**。
  · 输出统一带 `[OK]/[FAIL]`，退出码 0/1。
"""
import os
import subprocess
import sys
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

keyword = sys.argv[1] if len(sys.argv) > 1 else ""
files = sorted(f for f in os.listdir(TESTS_DIR)
               if f.startswith("test_") and f.endswith(".py") and keyword in f)
if not files:
    print("没有匹配 %r 的测试文件（%s）" % (keyword, TESTS_DIR))
    sys.exit(2)

env = dict(os.environ, PYTHONIOENCODING="utf-8", QT_QPA_PLATFORM="offscreen",
           AIPET_NO_SPAWN="1")
print("跑 %d 个体检文件（仓库：%s）\n" % (len(files), REPO))
rows, t_all = [], time.time()
for f in files:
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(TESTS_DIR, f)], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=900)
    dt = time.time() - t0
    out = (r.stdout or "") + (r.stderr or "")
    ok = out.count("[OK]")
    fail = out.count("[FAIL]")
    tail = ""
    for ln in out.splitlines():
        if "[FAIL]" in ln:
            tail = ln.strip()[:88]
            break
    if not tail and r.returncode != 0:
        tail = (out.strip().splitlines() or ["(无输出)"])[-1][:88]
    rows.append((f, r.returncode, ok, fail, dt, tail))

print("%-30s %-6s %-7s %-7s %s" % ("文件", "rc", "OK", "FAIL", "耗时"))
print("-" * 92)
bad = 0
for f, rc, ok, fail, dt, tail in rows:
    print("%-30s %-6d %-7d %-7d %.1fs %s" % (f, rc, ok, fail, dt, tail))
    if rc != 0:
        bad += 1
print("-" * 92)
print("总计 %d 个文件 / %d 项通过 / %d 个文件失败 / %.1fs"
      % (len(rows), sum(r[2] for r in rows), bad, time.time() - t_all))
if bad:
    print("有失败 → 退出码 1（详情跑单个文件看）")
    sys.exit(1)
print("全部通过 ✓")
sys.exit(0)
