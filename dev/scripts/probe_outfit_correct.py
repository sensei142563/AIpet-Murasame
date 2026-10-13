# -*- coding: utf-8 -*-
"""决定性验证（写对位置）：pets.murasame.a.cloth 逐套改 → 四套渲染占比是否不同？"""
import io
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
d0 = json.loads(orig)
print("PET_KEYS", list((d0.get("pets") or {}).keys())[:4],
      "| set a of murasame:", ((d0.get("pets") or {}).get("murasame") or {}).get("a"))
pet = Murasame()


def opaque(p):
    img = p.grab().toImage()
    n = cnt = 0
    for x in range(0, img.width(), 3):
        for y in range(0, img.height(), 3):
            cnt += 1
            if img.pixelColor(x, y).alpha() > 32:
                n += 1
    return round(100.0 * n / max(1, cnt), 2)


out = {}
try:
    for c in ("制服", "睡衣", "私服", "刀服"):
        d = json.loads(orig)
        blk = d.setdefault("pets", {}).setdefault("murasame", {}).setdefault("a", {})
        blk["cloth"] = c
        io.open(pc, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
        o = PO.load_outfit()
        pet.update_portrait(pet.portrait_target, pet.first_portrait)
        out[c] = opaque(pet)
        print("CLOTH", c, "-> load_outfit", o.get("cloth"), o.get("cloth_id"), "| opaque", out[c])
finally:
    io.open(pc, "w", encoding="utf-8").write(orig)
print("DISTINCT", len(set(out.values())), out)
'''.replace("__ROOT__", ROOT)

r = subprocess.run([VENV, "-c", CODE], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=1200)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s = l.strip()
    if s.startswith(("PET_KEYS", "CLOTH", "DISTINCT")) or "Error" in s:
        print("   " + s[:170])
