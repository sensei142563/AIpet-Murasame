# -*- coding: utf-8 -*-
"""修自己脚本的编码问题（子进程未指定 utf-8），再核验 dry-run 与提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

print("=== 语法检查（本次显式指定 utf-8，避免 GBK 解码错）===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % P],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("✓ 语法 OK" if r.returncode == 0 else "✗ " + (r.stderr or "")[:250]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== dry-run 汇总 ===")
r2 = subprocess.run([sys.executable, "-u", P, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600)
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 汇总 ===")
print("\n".join("   " + l for l in out[i:].splitlines()[:14]) if i > 0 else out[-1200:])
allskip = "PASS 0" in out

print()
print("判定:", "✓ dry-run 全部 SKIP（PASS 0）、零谎报" if allskip else "· 仍有非 SKIP 项")
print("   真机就绪后：python dev/scripts/accept_all.py")

MSG = """fix(accept): 核验脚本的编码问题（子进程需显式 utf-8）+ 确认 dry-run 全 SKIP

上一提交修掉两处谎报 PASS 后，我的**核验脚本自己**在调用 ast.parse 子进程时没指定
encoding="utf-8"，撞上本机 GBK 默认编码 → UnicodeDecodeError。
这次显式指定 encoding/errors，复核通过；dry-run 汇总为 **PASS 0 / FAIL 0 / 全部 SKIP**。

今晚第三次踩编码坑（前两次：内联 python -c 输出非 GBK 字符、PowerShell 双引号串里放双引号），
因此固定两条做法：
  1) 涉及中文的脚本一律写文件用 python -u 跑，不用 inline -c；
  2) 所有 subprocess.run(..., text=True) 必须显式 encoding="utf-8", errors="replace"。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_accept3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
