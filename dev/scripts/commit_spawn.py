# -*- coding: utf-8 -*-
"""跑全量并提交桌宠启动路径的统一。"""
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

MSG = """fix(launcher): 桌宠启动也走共用的 _spawn_console + _watch_child（与微信/QQ 一致）

问题（test_qt_lifecycle B1 段，三条里只有"桌宠"那条红）：
  pcl_launcher/silicon_window.py 的 `_launch_pet()` 用的是**裸 Popen**：
      self.shell._pet_proc = subprocess.Popen([py, os.path.join(base, "run.py")], cwd=base,
                                              creationflags=_spawn_flags())
  而微信桥接 / QQ 桥接都走共用的 `self._spawn_console(...)` + `self._watch_child(...)`。

为什么这是真问题（不是"风格不统一"）：
  · `_spawn_console` 在 Windows 上会套一层 `cmd /k` —— 子进程退出后**控制台留在屏幕上**，
    报错看得清；裸 Popen + CREATE_NEW_CONSOLE 则是**一闪就关**，主人根本来不及看。
  · `_watch_child` 会在 1.8 秒后回查：还在跑就什么都不做；已经死了就把**退出码 + 常见原因**
    摆到启动器界面上。
  这正是用户当年报过的「点启动微信秒卡退，界面上什么都没说」的同一个毛病 ——
  微信/QQ 两处已经修过，**桌宠自己这条漏了**。

改法：`_launch_pet()` 改为
    self.shell._pet_proc = self._spawn_console(py, os.path.join(base, "run.py"), base)
    self._watch_child(self.shell._pet_proc, "桌宠", "常见原因：…依赖没装全 / 28565 被占 / 杀软拦截…")

验证：
  · `tests/test_qt_lifecycle.py` 的 B1 段**全绿**：桌宠 / 微信 / QQ 三处都走共用方法、
    全仓只剩一处裸 CREATE_NEW_CONSOLE（在共用方法里）、Windows 上套 cmd /k、
    没有别的裸 Popen 起控制台程序。
  · 改动的文件通过 py_compile。
  · 该文件整体仍红 6 项，都在 A2 的 agent 行为段（下一轮处理）。
"""
p = os.path.join(MAP, "_msg_spawn.txt")
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
