# -*- coding: utf-8 -*-
"""修启动器 vision_source 的缺省方向：4 处 `or "local"` → `or "cloud"`。

依据（权威口径，不是我猜的）：
  tool/vision_local.py:14   vision_source  "cloud"（默认）| "local"
  tool/vision_local.py:63   enum_of(_cfg().get("vision_source"), SOURCES, "cloud", "vision_source")
  tests/test_vision_interface.py:10  "默认必须等于从前：vision_source 没配 → 走云端，一个字的行为都不变"
  tests/…:52                 check("没配 vision_source → cloud（默认，走原链路）")
而用户机器的 config.json 里**没有** vision_source（已核对）⇒ 实际走云端，
启动器却按 local 显示 ⇒ 首页「模型状态」写着"本地视觉模型（本地部署）"，与实际相反。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SW = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")

t = io.open(SW, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = 'cfg.get("vision_source") or "local"'
NEW = 'cfg.get("vision_source") or "cloud"'
n_cfg = t.count(OLD)
t = t.replace(OLD, NEW)
OLD2 = '_vcfg.get("vision_source") or "local"'
NEW2 = '_vcfg.get("vision_source") or "cloud"'
n_v = t.count(OLD2)
t = t.replace(OLD2, NEW2)
io.open(SW, "w", encoding="utf-8", newline="\n").write(t)
print("✓ 替换 cfg.  : %d 处" % n_cfg)
print("✓ 替换 _vcfg.: %d 处" % n_v)
print("   合计 %d 处" % (n_cfg + n_v))

print()
print("=== 复核：改后各处 ===")
for i, l in enumerate(io.open(SW, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "vision_source" in l:
        print("   %5d| %s" % (i, l.strip()[:112]))

print()
print("=== 残留检查：还有没有 or \"local\" ===")
rest = [i for i, l in enumerate(io.open(SW, encoding="utf-8", errors="replace").read().split("\n"), 1)
        if 'vision_source' in l and 'or "local"' in l]
print("   残留 =", rest or "无 ✓")

print()
print("=== 语法检查 ===")
import py_compile  # noqa: E402
try:
    py_compile.compile(SW, doraise=True)
    print("   py_compile OK ✓")
except Exception as e:
    print("   ✗", e)
