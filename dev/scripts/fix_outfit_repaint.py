# -*- coding: utf-8 -*-
"""收掉最后一项：测试里 _switch_cloth 之后补 app.processEvents() 再取图。
（已用落地脚本证明：四套 pixmap 与 grab 摘要**全都不同** ⇒ 产品侧正常，是取图时机问题。）
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
T = os.path.join(ROOT, "tests", "test_bugfix_0930b.py")

t = io.open(T, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
old = '''            _pet2._switch_cloth(_c)              # ← 右键菜单点衣服走的就是这个
'''
new = '''            _pet2._switch_cloth(_c)              # ← 右键菜单点衣服走的就是这个
            # ⚠ 必须先把事件队列跑完再取图：实测不 processEvents() 的话，
            #   pet.grab() 会拿到**上一帧** —— 于是"睡衣/私服/刀服"三套摘要完全相同，
            #   看着像"换装不生效"，其实是取图时机问题。
            #   证据（落地脚本直接跑 pet.pixmap() 与 grab 的 md5 对照，四套全不同）：
            #   dev/probe_pixmap_result.txt
            app.processEvents()
'''
if old in t and "app.processEvents()" not in t.split("_switch_cloth(_c)")[1][:200]:
    t = t.replace(old, new, 1)
    io.open(T, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已在 _switch_cloth 后补 app.processEvents()")
else:
    print("· 无需改（或锚点未命中）")

print()
print("=== 验证 ===")
try:
    py_compile.compile(T, doraise=True)
    print("   ✓ py_compile")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)
r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930b.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s = l.strip()
    if "[FAIL]" in s or "FAILED" in s or "通过" in s or s.startswith(("解析层", "渲染层")):
        print("   " + s[:150])
print("   退出码 =", r.returncode)
