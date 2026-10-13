# -*- coding: utf-8 -*-
"""精确查清三处差异，准备恢复：① decor_rules 真实位置 ② plugins.py 函数级差异 ③ colors.py 缺什么。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
CUR_BRANCH = "HEAD"
REF_MAIN = "remotes/origin/main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"


def show(ref, path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


def funcs(t):
    return set(re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", t, re.M))


print("=== ① decor_rules 在 natsume pet.json 里的原始出现 ===")
for ref, label in ((CUR_BRANCH, "当前树(文件)"), (REF_MAIN, "origin/main"), (REF_BAK, "覆盖前备份")):
    if ref == CUR_BRANCH:
        p = os.path.join(ROOT, "pets", "natsume", "pet.json")
        t = io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
    else:
        t = show(ref, "pets/natsume/pet.json")
    hits = [l.strip()[:110] for l in t.split("\n") if "decor" in l.lower()]
    print("   %-14s decor 相关行 %d 条 %s" % (label, len(hits), hits[:4]))

print()
print("=== ② tool/plugins.py 函数级差异 ===")
cur = io.open(os.path.join(ROOT, "tool", "plugins.py"), encoding="utf-8", errors="replace").read()
f_cur, f_main, f_bak = funcs(cur), funcs(show(REF_MAIN, "tool/plugins.py")), funcs(show(REF_BAK, "tool/plugins.py"))
print("   当前树函数 %d 个" % len(f_cur))
print("   origin/main 函数 %d 个，备份 %d 个" % (len(f_main), len(f_bak)))
print("   **当前树缺**（origin/main 或备份里有）:")
for x in sorted((f_main | f_bak) - f_cur):
    print("        - %s" % x)
print("   （当前树独有、两边都没有的）:", sorted(f_cur - (f_main | f_bak)) or "无")
print("   备份 == origin/main 的函数集合？", "是 ✓" if f_bak == f_main else "不同 ✗")

print()
print("=== ③ pcl_launcher/colors.py：备份里的 secondary_text 长什么样 ===")
bak_c = show(REF_BAK, "pcl_launcher/colors.py")
cur_c = io.open(os.path.join(ROOT, "pcl_launcher", "colors.py"), encoding="utf-8",
                errors="replace").read()
i = bak_c.find("secondary_text")
if i >= 0:
    lo = bak_c.rfind("\n", 0, max(0, i - 300))
    print(bak_c[max(0, lo):i + 400])
print("   --- 当前树里与之相邻的部分（看是不是整块丢了）---")
for key in ("SECONDARY", "secondary", "sub_text", "SUB_TEXT", "TEXT_DIM"):
    if key in cur_c:
        print("      当前树有:", key)
