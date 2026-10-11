# -*- coding: utf-8 -*-
"""补 api.py 的 import time，然后重跑 stt_1.py 的验证部分（stt_1 会跳过已存在的 /stt）。"""
import io
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
API = MAIN + r"\api.py"

s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
if re.search(r"^import time$", s, re.M):
    print("· api.py 已有 import time")
else:
    # 放在第一个 import 行之后，最稳
    lines = s.split("\n")
    idx = next((i for i, l in enumerate(lines) if l.startswith("import ") or l.startswith("from ")), 0)
    lines.insert(idx, "import time")
    s = "\n".join(lines)
    io.open(API, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已补 import time（第 %d 行）" % (idx + 1))

print()
print("=== 重跑 STT 验证 ===")
r = subprocess.run([sys.executable, "-u", MAIN + r"\dev\scripts\stt_1.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== 用预生成台词")
print(out[i:] if i >= 0 else out[-3000:])
