# -*- coding: utf-8 -*-
"""给 tool/state.py 补 reset_cache()（备份里有、我们这棵树没有），然后跑最后一项测试。"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
P = os.path.join(ROOT, "tool", "state.py")

t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "def reset_cache" in t:
    print("· 已有 reset_cache")
else:
    add = '''

def reset_cache():
    """丢掉「状态文件」的内存缓存，强制下一次读取重新读盘。

    ⚠ 本模块的状态读取**本来就没有缓存**（每次 `_load()` 直接读文件），
      所以这里目前是**空操作** —— 保留它，是为了让「换了文件路径 → 重新读」
      这个调用契约稳定：测试与外部脚本都按这个契约调用（例如把 `_store_path`
      指到临时文件后调一次，确保不会读到旧的）。
      将来若给 `_load()` 加缓存，**必须**在这里把它清掉，否则那些调用会读到旧数据。
    """
    return None
'''
    t = t.rstrip("\n") + add
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已在 tool/state.py 末尾补 reset_cache()（带说明的空操作）")

print()
print("=== 验证 ===")
try:
    py_compile.compile(P, doraise=True)
    print("   ✓ py_compile tool/state.py")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:250])
    sys.exit(1)

code = ("import sys;sys.path.insert(0,r'%s');"
        "import tool.state as S;"
        "print('HAS_RESET', callable(getattr(S,'reset_cache',None)))" % ROOT)
r = subprocess.run([VENV, "-c", code], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "HAS_RESET" in l or "Error" in l:
        print("   " + l.strip()[:140])

r2 = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930b.py")], cwd=ROOT,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = ((r2.stdout or "") + (r2.stderr or "")).split("\n")
for l in out:
    if "[FAIL]" in l or "FAILED" in l or "通过" in l or "Error" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r2.returncode)
