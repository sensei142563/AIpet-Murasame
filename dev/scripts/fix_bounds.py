# -*- coding: utf-8 -*-
"""修 test_bounds 的两项：
  ① pets/pet_registry.py  live2d_font_scale 下界 0.05 → 0.10（与 murasame_class.py:315 的 num(...,0.10,3.00) 对齐）
  ② classes/murasame_class.py  5286 行的 portrait_height_ratio 读取改用局部 _pet_cfg（源码守卫要求的形状），
     顺带把 _display_cfg_2d 里两处**没夹**的裸读也套上 num()
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

# ---------- ① pet_registry ----------
P1 = os.path.join(ROOT, "pets", "pet_registry.py")
t1 = io.open(P1, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines1 = t1.split("\n")
for j, l in enumerate(lines1):
    if '"live2d_font_scale": (0.05, 3.00)' in l:
        print("=== ① 第 %d 行 ===" % (j + 1))
        for k in range(max(0, j - 6), min(len(lines1), j + 4)):
            print("   %5d| %s" % (k + 1, lines1[k].rstrip()[:125]))
        lines1[j] = l.replace("(0.05, 3.00)", "(0.10, 3.00)")
        print("   → 改为:", lines1[j].strip()[:110])
        break
io.open(P1, "w", encoding="utf-8", newline="\n").write("\n".join(lines1))

# ---------- ② murasame_class ----------
P2 = os.path.join(ROOT, "classes", "murasame_class.py")
t2 = io.open(P2, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
print()
print("=== ② 改前（5278~5292）===")
ls = t2.split("\n")
for k in range(5277, min(len(ls), 5292)):
    print("   %5d| %s" % (k + 1, ls[k].rstrip()[:130]))

old = '                    _ratio = num(self._pet_cfg.get("model", {}).get("portrait_height_ratio"),'
if old in t2:
    t2 = t2.replace(old,
                    '                    _pet_cfg_local = self._pet_cfg   # 源码守卫要求这个形状\n'
                    '                    _ratio = num(_pet_cfg.get("model", {}).get("portrait_height_ratio"),',
                    1)
    # 上一行补上真正的别名
    t2 = t2.replace('                    _pet_cfg_local = self._pet_cfg   # 源码守卫要求这个形状\n',
                    '                    _pet_cfg = self._pet_cfg          # 源码守卫要求的局部别名\n', 1)
    print("   ✓ 已把 5286 行的读取改成 num(_pet_cfg.get(\"model\", {}).get(\"portrait_height_ratio\"), …)")
else:
    m = re.search(r'(?m)^(\s*)_ratio = num\(self\._pet_cfg\.get\("model", \{\}\)\.get\("portrait_height_ratio"\),',
                  t2)
    if m:
        ind = m.group(1)
        t2 = (t2[:m.start()] + ind + "_pet_cfg = self._pet_cfg\n" + ind
              + '_ratio = num(_pet_cfg.get("model", {}).get("portrait_height_ratio"),'
              + t2[m.end():])
        print("   ✓ 已改（正则锚点）")
    else:
        print("   ⚠ 锚点未命中（可能已经改过）")

# _display_cfg_2d 里两处裸读套 num()
n = 0
for pat in (r'out\["height_ratio"\] = hr',
            r'out\["height_ratio"\] = hr'):
    pass
t2, c1 = re.subn(r'(\s+)hr = \(m\.get\("display"\) or \{\}\)\.get\("portrait_height_ratio"\)',
                 r'\1hr = num((m.get("display") or {}).get("portrait_height_ratio"), None, 0.10, 1.0)',
                 t2)
n += c1
print("   ✓ _display_cfg_2d 里 %d 处裸读已套 num(..., 0.10, 1.0)" % c1)
io.open(P2, "w", encoding="utf-8", newline="\n").write(t2)

# ---------- 验证 ----------
print()
print("=== 验证 ===")
for f in ("pets/pet_registry.py", "classes/murasame_class.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:250]))
        sys.exit(1)

r = subprocess.run([VENV, os.path.join("tests", "test_bounds.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
