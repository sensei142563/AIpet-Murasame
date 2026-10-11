# -*- coding: utf-8 -*-
"""干净地重做：① 回退 accept_all.py 到已提交版本
   ② 重新加第 ⑨ 节
   ③ 用**整体缩进**的方式给 UI 段加全局前台守卫（不是 if/else 前缀 hack）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
S8 = os.path.join(MAIN, "dev", "scripts", "add_stability_section.py")

print("=== 回退 accept_all.py ===")
r = subprocess.run(["git", "-C", MAIN, "checkout", "--", "dev/scripts/accept_all.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + (r.stdout or r.stderr or "✓ 已回退").strip()[:120])

print()
print("=== 重新加第 ⑨ 节 ===")
r2 = subprocess.run([sys.executable, "-u", S8], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=900, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines():
    if re.search(r"已插入|锚点|FAIL|Error|SKIP ⑨|PASS ⑨", l):
        print("   " + l.strip()[:150])

print()
print("=== 给 UI 段加整体缩进的守卫 ===")
t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "SKIP_UI" in t and "if not SKIP_UI:" in t:
    print("· 已有")
else:
    # 找 UI 段边界：从 "    print(\"=== 3. 逐项验收 ===\")" 之后，到 "    # ===== ⑧" 之前
    i = t.find('print("=== 3. 逐项验收 ===")')
    j = t.find("# ===== ⑧")
    if i < 0 or j < 0:
        print("✗ 找不到 UI 段边界 i=%d j=%d" % (i, j))
        sys.exit(1)
    # i 所在行的行尾
    i_end = t.find("\n", i) + 1
    # j 所在行的行首
    j_start = t.rfind("\n", 0, j) + 1
    body = t[i_end:j_start]
    indented = "\n".join(("    " + ln) if ln.strip() else ln for ln in body.split("\n"))
    guard = ('''    # 【全局前台守卫】今天踩过的坑：我在你正用 QQ 的时候还去点你的屏幕，既干扰你、
    # 测出来的结果也不算数。规则：前台是**第三方应用**就整段跳过 UI 检查；只有在我们
    # 自己的 App 或桌面在前台时才点（桌面在前台时拉起 App 是安全的）。
    _fg0 = resumed_activity()
    SKIP_UI = (not DRY) and bool(_fg0) and (PKG not in _fg0) \\
        and ("launcher" not in _fg0.lower()) and ("unihome" not in _fg0.lower())
    if SKIP_UI:
        print("   ⚠ 当前前台是「%s」—— 你正在用别的应用，本轮跳过所有需要点击的检查" % _fg0)
        record("① 3D 页加载", "SKIP", "前台是别的应用，未点击")
        record("② 3D AR", "SKIP", "前台是别的应用，未点击")
        record("③ 首页 QQ 卡", "SKIP", "前台是别的应用，未点击")
        record("④ 返回键两次退出", "SKIP", "前台是别的应用，未点击")
        record("⑤/⑥ 设置页", "SKIP", "前台是别的应用，未点击")
    else:
''')
    t = t[:i_end] + guard + indented + t[j_start:]
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已把 UI 段整体缩进 4 空格并套上 if not SKIP_UI 的 else 分支")

print()
print("=== 语法检查 ===")
r3 = subprocess.run([sys.executable, "-c",
                     "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("OK" if r3.returncode == 0 else "FAIL\n" + (r3.stderr or "")[:500]))

if r3.returncode == 0:
    print()
    print("=== dry-run ===")
    r4 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=900,
                        env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (r4.stdout or "") + (r4.stderr or "")
    jj = out.find("=== 汇总")
    print(out[jj:] if jj > 0 else out[-700:])
