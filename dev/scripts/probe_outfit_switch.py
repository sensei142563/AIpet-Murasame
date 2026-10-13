# -*- coding: utf-8 -*-
"""决定性实验：换装到底生不生效？
  A) 按**测试的写法**（顶层 "b"）改 → 期望四套一样（说明测试写错了地方）
  B) 按**代码真正读的地方**（pets.<id>.b）改 → 若四套不同，则应用侧是好的，测试要改
只输出测量结果，不修改任何持久状态（结束时还原原文件）。
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

CODE = r'''
import io, json, os, sys
sys.path.insert(0, r"%s")
os.chdir(r"%s")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from tool import portrait_outfit as PO
from classes.murasame_class import Murasame

pc = PO.choice_path()
orig = io.open(pc, encoding="utf-8").read()
d0 = json.loads(orig)
print("STORE_KEYS", sorted(d0.keys()))
print("HAS_PETS_PART", bool(d0.get("pets")), list((d0.get("pets") or {}).keys())[:3])

pet = Murasame()
# 取活动角色 id
try:
    from pets.pet_registry import get_active_pet_id
    pid = get_active_pet_id()
except Exception as e:
    pid = "?"
print("ACTIVE_PID", pid)
print("CUR_SET", pet._current_set())


def opaque(p):
    try:
        pm = p.grab()
        img = pm.toImage()
        tot = img.width() * img.height()
        if not tot:
            return 0.0
        n = 0
        step = 3
        cnt = 0
        for x in range(0, img.width(), step):
            for y in range(0, img.height(), step):
                cnt += 1
                if img.pixelColor(x, y).alpha() > 32:
                    n += 1
        return 100.0 * n / max(1, cnt)
    except Exception as e:
        return -1.0


def measure(tag, mutate):
    out = {}
    try:
        for c in ("制服", "睡衣", "私服", "刀服"):
            d = json.loads(orig)
            mutate(d, c, pid)
            io.open(pc, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
            if hasattr(PO, "reset_cache"):
                PO.reset_cache()
            pet.update_portrait(pet.portrait_target, pet.first_portrait)
            out[c] = round(opaque(pet), 2)
        print(tag, out, "DISTINCT", len(set(out.values())))
    except Exception as e:
        import traceback; traceback.print_exc()
    finally:
        io.open(pc, "w", encoding="utf-8").write(orig)


# A) 测试的写法：顶层 "b"
measure("A_TOPLEVEL_B", lambda d, c, pid: d.setdefault("b", {}).__setitem__("cloth", c))


# B) 代码真正读的写法：pets.<pid>.<set>
def _mut_pets(d, c, pid):
    pets = d.setdefault("pets", {})
    blk = pets.setdefault(str(pid), {})
    blk.setdefault("b", {})["cloth"] = c


measure("B_PETS_PARTITION", _mut_pets)
''' % (ROOT, ROOT)

r = subprocess.run([VENV, "-c", CODE], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=1200)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if re.match(r"(STORE_KEYS|HAS_PETS_PART|ACTIVE_PID|CUR_SET|A_TOPLEVEL_B|B_PETS_PARTITION)", l.strip()) \
            or "Error" in l or "Traceback" in l:
        print("   " + l.strip()[:150])
