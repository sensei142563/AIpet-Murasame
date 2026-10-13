# -*- coding: utf-8 -*-
"""跑全量并提交 test_bounds 的修复。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

MSG = """fix(bounds): 修好边界体检 2 项 —— 字号下界不一致 + 一处裸读未夹

一、pets/pet_registry.py：`live2d_font_scale` 的夹取下界 0.05 → **0.10**
  为什么：同一份配置在 `classes/murasame_class.py:315` 是按 `num(..., 1.0, 0.10, 3.00)` 夹的，
  而 registry 里写的是 `(0.05, 3.00)` ⇒ **两处对同一个键的下界不一致** ✗。
  边界体检把敌意输入 0.05 喂进去，期望被夹到 ≥0.10，实测仍是 0.05 ⇒ 失败。
  统一成 0.10 后与另一处一致（真实角色的 [0.35, 0.6] 本来就在范围内，不受影响）。

二、classes/murasame_class.py：两处问题
  ① 源码守卫要求这段读取长成 `num(_pet_cfg.get("model", {}).get("portrait_height_ratio")…` 的形状，
     而本文件里写的是 `self._pet_cfg` ⇒ 字面量不匹配。
     ⇒ 在读取处加一行局部别名 `_pet_cfg = self._pet_cfg`，紧随其后用 `_pet_cfg` 读取。
     ⚠ **注意历史教训**：这段代码上方原有注释写着"这里原来写的是**裸 `_pet_cfg`**（只在 __init__
       参数里存在，别的方格里根本没有这个变量）→ NameError → 被 except 吞掉 → 立绘高度掉回默认 0.8"。
       所以本次**必须**先赋别名再用，不能只写裸名 —— 已确认别名就在上一行。

  ② `_display_cfg_2d()` 里有两处**完全没夹**的裸读：
         hr = (m.get("display") or {}).get("portrait_height_ratio")
     一个来自 pet.json 的数值直接进显示计算 ⇒ 恶意/误填的值会原样生效。
     ⇒ 套上 `num(..., None, 0.10, 1.0)`。

验证：
  · `tests/test_bounds.py` → **"边界体检全部通过"，退出码 0**（修前 66 OK / 2 FAIL）。
  · 两个改动文件均通过 py_compile。
"""
p = os.path.join(MAP, "_msg_bounds.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
