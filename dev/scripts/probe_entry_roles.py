# -*- coding: utf-8 -*-
"""核实 api.py / main.py / run.py 各自到底是什么角色（README 1430 行那句话疑似错位）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

for f in ("api.py", "main.py", "run.py"):
    p = os.path.join(ROOT, f)
    print("=== %s ===" % f)
    if not os.path.isfile(p):
        print("   ✗ 不存在")
        continue
    src = io.open(p, encoding="utf-8", errors="replace").read()
    # 模块 docstring
    m = re.search(r'^(?:#![^\n]*\n)?(?:#[^\n]*\n)*\s*(?:"""|\'\'\')([\s\S]{0,400}?)(?:"""|\'\'\')', src)
    if m:
        for l in m.group(1).strip().split("\n")[:6]:
            print("   doc: " + l.strip()[:96])
    # 关键特征
    feats = []
    if "FastAPI(" in src or "from fastapi" in src or "uvicorn" in src:
        feats.append("FastAPI/uvicorn（后端接口）")
    if "QApplication" in src or "QMainWindow" in src or "murasame_class" in src:
        feats.append("PyQt 图形界面")
    if "subprocess" in src and ("Popen" in src or "run(" in src):
        feats.append("拉起子进程")
    if "create_window" in src or "QtWidgets" in src:
        feats.append("Qt 控件")
    if "venv" in src and ("install" in src or "requirements" in src):
        feats.append("环境安装")
    print("   特征: " + ("、".join(feats) if feats else "（没抓到明显特征）"))
    print("   行数: %d" % len(src.split("\n")))
    print()
