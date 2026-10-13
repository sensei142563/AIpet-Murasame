# -*- coding: utf-8 -*-
"""打印备份里 /agent 分发处的上下文，以及 AgentWorker 类的完整块，为插入做准备。"""
import io
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF = "remotes/origin/backup/main-before-overwrite-20261001"


def show(path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (REF, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


mc = show("classes/murasame_class.py").split("\n")
i = next(k for k, l in enumerate(mc) if l.strip().startswith("if _t.lower().startswith(\"/agent \")"))
print("=== 备份里 /agent 分发处（前后各 14 行）===")
for j in range(max(0, i - 14), min(len(mc), i + 12)):
    print("%5d| %s" % (j + 1, mc[j].rstrip()[:135]))

print()
wk = show("classes/Worker_class.py").split("\n")
k = next(k for k, l in enumerate(wk) if l.startswith("class AgentWorker"))
end = len(wk)
for j in range(k + 1, len(wk)):
    if wk[j].startswith("class ") or (wk[j].strip() and not wk[j].startswith((" ", "\t", "#")) and
                                      not wk[j].startswith("class")):
        end = j
        break
print("=== 备份里 AgentWorker 类（第 %d~%d 行，共 %d 行）===" % (k + 1, end, end - k))
for j in range(k, end):
    print("%5d| %s" % (j + 1, wk[j].rstrip()[:135]))
