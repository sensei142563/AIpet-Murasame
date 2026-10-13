# -*- coding: utf-8 -*-
"""修掉上一步画蛇添足的 import：原文件是 `from .colors import *`（通配已含 fill_for_text），
我加成了 `import *, fill_for_text` ⇒ 语法错。把该行还原，保留 {fill_for_text(Color3).name()} 的替换。
"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

for rel in ("pcl_launcher/plugins_panel.py", "pcl_launcher/widgets.py"):
    P = os.path.join(ROOT, rel)
    t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    before = t
    t = t.replace("from .colors import *, fill_for_text", "from .colors import *")
    t = t.replace("from pcl_launcher.colors import *, fill_for_text", "from pcl_launcher.colors import *")
    if t != before:
        io.open(P, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ %s：import 行已还原为通配导入" % rel)
    else:
        print("· %s：无需修" % rel)
    # 确认 fill_for_text 现在可用（通配导入 → 直接可用）
    print("   含 fill_for_text 调用 %d 处；import 行：%s"
          % (t.count("fill_for_text("),
             next((l.strip() for l in t.split("\n") if "colors import" in l), "?")))

print()
print("=== 验证 ===")
for f in ("pcl_launcher/plugins_panel.py", "pcl_launcher/widgets.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:250]))
        sys.exit(1)

# 真导入一次（能不能拿到 fill_for_text）
code = ("import sys;sys.path.insert(0,r'%s');"
        "import pcl_launcher.widgets as W, pcl_launcher.plugins_panel as P;"
        "print('IMPORT_OK', hasattr(W,'fill_for_text'))" % ROOT)
r = subprocess.run([VENV, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "IMPORT_OK" in l or "Error" in l:
        print("   " + l.strip()[:140])

r2 = subprocess.run([VENV, os.path.join("tests", "test_frontend_style.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r2.returncode)
