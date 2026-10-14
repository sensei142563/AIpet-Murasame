# -*- coding: utf-8 -*-
"""修回合并不小心覆盖掉的那处 → 跑自检 → 绿了才推 main。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(a, timeout=2400):
    r = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return ((r.stdout or "") + (r.stderr or "")).strip(), r.returncode


P = os.path.join(ROOT, "classes", "murasame_class.py")
t = io.open(P, encoding="utf-8", errors="replace").read()
OLD = """        if not self.is_dnd_enabled():
            self.pause_all_ai(stop_voice=False)
        super().focusInEvent(event)"""
NEW = """        if not self.is_dnd_enabled():
            # ★ 2026-10-14：合并远端 main 时这处被自动采用成 pause_all_ai(stop_voice=False)。
            #   我们早先**故意**改成走默认参数（默认就是 stop_voice=False，语义更直白，
            #   测试 test_bugfix_0930b 也是查这个形状）⇒ 保持我们的写法。
            self.pause_all_ai()
        super().focusInEvent(event)"""
print("=== ① 改回我们的写法 ===")
if OLD in t:
    io.open(P, "w", encoding="utf-8", newline="\n").write(t.replace(OLD, NEW, 1))
    print("   ✓ 已改回 self.pause_all_ai()")
else:
    print("   ✗ 锚点未命中，看看现在是什么：")
    ls = t.split("\n")
    for i, l in enumerate(ls, 1):
        if "focusInEvent" in l:
            for j in range(i - 1, min(len(ls), i + 8)):
                print("      %5d| %s" % (j + 1, ls[j].rstrip()[:100]))
            break
import py_compile  # noqa: E402
try:
    py_compile.compile(P, doraise=True)
    print("   ✓ py_compile OK")
except Exception as e:
    print("   ✗ py_compile: %s" % e)
    sys.exit(1)

print()
print("=== ② 再跑 389 项自检 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=2400)
out = (r.stdout or "") + (r.stderr or "")
for l in out.strip().split("\n")[-3:]:
    if l.strip():
        print("   " + l.strip()[:120])
ok = "0 个文件失败" in out
if not ok:
    print("   仍失败项：")
    for l in out.split("\n"):
        if "[FAIL]" in l:
            print("      " + l.strip()[:120])

if ok:
    print()
    print("=== ③ 提交这个修正 ===")
    MSG = """fix(merge): 保留我们对 focusInEvent 的写法 —— 合并时被自动采用成他们的旧写法

## 现象
`git merge -X ours origin/main` 后自检由 389 掉到 388：
`test_bugfix_0930b.py` 的「focusInEvent 走的是默认路径（没传 stop_voice=True）」失败。

## 原因
`classes/murasame_class.py::focusInEvent` 这处**不是冲突区**，被自动合并采用了他们的版本：
```
他们    ：self.pause_all_ai(stop_voice=False)
我们    ：self.pause_all_ai()        ← 早先**故意**改的（默认即 stop_voice=False，语义更直白）
```
依据我们自己的 `dev/scripts/commit_stopvoice.py`：那次是刻意把
`pause_all_ai(stop_voice=False)` 改成 `pause_all_ai()`，并且**测试就是查这个形状**。

## 本次
改回我们的写法 + 加注释说明为什么，自检回到 389 全绿后再推 main。
"""
    p = os.path.join(ROOT, "dev", "merge-map", "_msg_mergefix.txt")
    io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
    sh(["git", "add", "-A"])
    o, c = sh(["git", "commit", "-F", p])
    print("   " + ((o.splitlines()[0] if o else "")[:130]))

    print()
    print("=== ④ 推 main ===")
    o2, c2 = sh(["git", "push", "origin", "HEAD:main"], timeout=3600)
    for l in o2.split("\n")[-8:]:
        if l.strip():
            print("   " + l.strip()[:130])
    print("   退出码 = %d" % c2)
    o3, _ = sh(["git", "ls-remote", "--heads", "origin"])
    for l in o3.split("\n"):
        if "refs/heads/" in l:
            print("   " + l.strip()[:110])
else:
    print()
    print("=== 自检没过 ⇒ 不推 main。合并结果留在本地 ===")
