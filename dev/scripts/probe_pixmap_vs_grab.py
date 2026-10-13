# -*- coding: utf-8 -*-
"""区分"产品 bug"还是"取图/重画假象"：
  每次 _switch_cloth 之后，直接对 QLabel 的 **pixmap()** 取摘要（绕开 widget 重画），
  并额外对比 grab() 的摘要。两者若不一致 ⇒ 是 grab/重画的问题，不是合成的问题。
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

CODE = r'''
import io, json, os, sys, hashlib
sys.path.insert(0, r"__ROOT__")
os.chdir(r"__ROOT__")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from tool import portrait_outfit as PO
from classes.murasame_class import Murasame


def dig_img(img):
    if img is None or img.isNull():
        return "null"
    buf = bytearray()
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            buf += bytes((c.red(), c.green(), c.blue(), c.alpha()))
    return hashlib.md5(bytes(buf)).hexdigest()[:10]


pc = PO.choice_path()
orig = io.open(pc, encoding="utf-8").read()
pet = Murasame()
try:
    for c in ("制服", "睡衣", "私服", "刀服"):
        pet._switch_cloth(c)
        pm = pet.pixmap()
        lbl = dig_img(pm.toImage() if pm is not None else None)
        app.processEvents()
        grb = dig_img(pet.grab().toImage())
        print("SW", c, "| pixmap", lbl, "| grab", grb,
              "| size", (pm.width(), pm.height()) if pm is not None else None)
finally:
    io.open(pc, "w", encoding="utf-8").write(orig)
'''.replace("__ROOT__", ROOT)

r = subprocess.run([VENV, "-c", CODE], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=1200)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s = l.strip()
    if s.startswith("SW") or "Error" in s or "Traceback" in s:
        print("   " + s[:160])
