# -*- coding: utf-8 -*-
"""对照实验：换装后 pet.pixmap()（QLabel 里真正设进去的图）对比 pet.grab()。
作为**独立脚本直接跑**（不再用 python -c 拼长串 —— 上次那样跑 0 输出）。

跑法：runtime\venv\Scripts\python.exe dev\scripts\probe_pixmap_vs_grab2.py
输出：写到 dev/probe_pixmap_result.txt，同时打印。
"""
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT = os.path.join(ROOT, "dev", "probe_pixmap_result.txt")
lines = []


def say(s):
    lines.append(str(s))
    print(s, flush=True)


say("== 换装 pixmap vs grab 对照 ==")
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    from tool import portrait_outfit as PO
    from classes.murasame_class import Murasame

    def dig(path_or_img):
        try:
            img = path_or_img.toImage() if hasattr(path_or_img, "toImage") else path_or_img
            if img is None or img.isNull():
                return "null"
            buf = bytearray()
            for y in range(0, img.height(), 2):
                for x in range(0, img.width(), 2):
                    c = img.pixelColor(x, y)
                    buf += bytes((c.red(), c.green(), c.blue(), c.alpha()))
            return hashlib.md5(bytes(buf)).hexdigest()[:10]
        except Exception as e:
            return "err:%s" % e

    pc = PO.choice_path()
    orig = io.open(pc, encoding="utf-8").read()
    pet = Murasame()
    try:
        for c in ("制服", "睡衣", "私服", "刀服"):
            pet._switch_cloth(c)
            app.processEvents()
            pm = pet.pixmap()
            say("SW %-4s | pixmap %-12s | grab %-12s | size %s"
                % (c, dig(pm), dig(pet.grab()),
                   (pm.width(), pm.height()) if pm is not None else None))
    finally:
        io.open(pc, "w", encoding="utf-8").write(orig)
except Exception as e:
    import traceback
    say("EXC %s: %s" % (type(e).__name__, e))
    say(traceback.format_exc()[:2000])

io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("WROTE", OUT)
