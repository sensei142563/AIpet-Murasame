# -*- coding: utf-8 -*-
"""定位 _run_agent_task 的调用链：备份里谁调它、当前树对应位置是什么。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"
SKIP = ("\\.venv\\", "\\.git\\", "site-packages", "__pycache__", "\\runtime\\", "\\dev\\scripts\\")


def show(ref, path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


print("=== 备份里 _run_agent_task / _on_agent_done / _agent_worker 的所有出现 ===")
for path in ("classes/murasame_class.py", "main.py", "classes/Worker_class.py",
             "tool/agent_bridge.py", "qq/qq_chat.py", "chat.py"):
    t = show(REF_BAK, path)
    if not t:
        continue
    for i, l in enumerate(t.split("\n"), 1):
        if re.search(r"_run_agent_task|_on_agent_done|AgentWorker|agent_worker", l):
            print("   %-30s %5d| %s" % (path, i, l.strip()[:120]))

print()
print("=== 当前树里同样关键字的出现 ===")
for dp, dn, fn in os.walk(ROOT):
    if any(s in dp + "\\" for s in SKIP):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        for i, l in enumerate(t.split("\n"), 1):
            if re.search(r"_run_agent_task|_on_agent_done|AgentWorker|agent_worker|/agent", l):
                print("   %-34s %5d| %s" % (f, i, l.strip()[:115]))

print()
print("=== 备份里 /agent 命令是在哪儿分发的 ===")
for path in ("classes/murasame_class.py", "chat.py", "main.py"):
    t = show(REF_BAK, path)
    for i, l in enumerate(t.split("\n"), 1):
        if "/agent" in l or "agent" in l.lower() and ("startswith" in l or "cmd" in l.lower()):
            print("   %-30s %5d| %s" % (path, i, l.strip()[:120]))
