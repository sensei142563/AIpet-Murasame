# -*- coding: utf-8 -*-
"""定位换装失效是在「解析」还是「渲染」：
  逐套写 portrait_choice.json，打印 load_outfit() 的结果与 pet 实际用的图层号。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

CODE = r'''
import io, json, os, sys
sys.path.insert(0, r"__ROOT__")
os.chdir(r"__ROOT__")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from tool import portrait_outfit as PO
from classes.murasame_class import Murasame

pc = PO.choice_path()
orig = io.open(pc, encoding="utf-8").read()
pet = Murasame()
print("CLOTHES_TABLE_A", {k: v[0] for k, v in (PO.CLOTHES_BY_SET.get("a") or {}).items()})
try:
    for c in ("制服", "睡衣", "私服", "刀服"):
        d = json.loads(orig)
        d.setdefault("a", {})["cloth"] = c
        io.open(pc, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
        o = PO.load_outfit()
        # 再看 pet 实际拿去显示的图层
        try:
            layers = pet._current_layers() if hasattr(pet, "_current_layers") else None
        except Exception as e:
            layers = "ERR:%s" % e
        if layers is None:
            layers = getattr(pet, "_layers", None) or getattr(pet, "layers", None)
        print("CLOTH", c, "->", {k: o.get(k) for k in ("cloth", "cloth_id", "hair")},
              "| pet_layers", layers)
finally:
    io.open(pc, "w", encoding="utf-8").write(orig)
'''.replace("__ROOT__", ROOT)

r = subprocess.run([VENV, "-c", CODE], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=1200)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s = l.strip()
    if s.startswith(("CLOTH", "CLOTHES_TABLE_A")) or "Error" in s or "Traceback" in s:
        print("   " + s[:170])
