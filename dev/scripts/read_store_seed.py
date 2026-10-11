# -*- coding: utf-8 -*-
"""读 Store 的 seedPetsIfNeeded / copyAssetDir / listPets 三段确切实现。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
F = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame/Store.kt")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
for a, b, title in ((22, 80, "init / seedPetsIfNeeded / copyAssetDir"),
                    (132, 160, "listPets")):
    print("=== %s（%d~%d）===" % (title, a, b))
    for i in range(a - 1, min(len(lines), b)):
        print("%4d| %s" % (i + 1, lines[i].rstrip()[:150]))
    print()
