# -*- coding: utf-8 -*-
"""给 api.py 补 import re，然后重跑 qq_bridge_1.py 的验证（它会跳过已存在的路由）。"""
import io
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
API = MAIN + r"\api.py"

s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
if re.search(r"^import re$", s, re.M):
    print("· 已有 import re")
else:
    lines = s.split("\n")
    idx = next((i for i, l in enumerate(lines) if l.startswith("import ")), 0)
    lines.insert(idx, "import re")
    io.open(API, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("✓ 已补 import re（第 %d 行）" % (idx + 1))

print()
r = subprocess.run([sys.executable, "-u", MAIN + r"\dev\scripts\qq_bridge_1.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== ① /qq/status")
print(out[i:] if i >= 0 else out[-2500:])
