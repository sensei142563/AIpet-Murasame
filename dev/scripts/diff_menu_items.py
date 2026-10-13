# -*- coding: utf-8 -*-
"""抽取右键菜单项清单：现在的工作区 vs 覆盖前备份（backup/main-before-overwrite-20261001）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
OLD = "backup/main-before-overwrite-20261001"
CUR = os.path.join(ROOT, "classes", "murasame_class.py")
ITEM_PAT = re.compile(r'(?:item|section|submenu|addAction|menu\.addAction)\s*\(\s*[^,)]*?["\']([^"\']{1,40})["\']')


def extract(text, label):
    print("=== %s ===" % label)
    # 找到菜单构造区域：从 StoryMenu( 或 右键 出现处起，取后续 200 行
    idx = None
    for m in re.finditer(r"StoryMenu\(|def .*menu|右键", text):
        idx = m.start()
        break
    seg = text
    items = ITEM_PAT.findall(seg)
    seen = []
    for it in items:
        if it not in seen:
            seen.append(it)
    print("   菜单类条目共 %d 个：" % len(seen))
    for it in seen[:80]:
        print("      • " + it)
    return seen


cur_txt = io.open(CUR, encoding="utf-8", errors="replace").read()
cur_items = extract(cur_txt, "现在（工作区）")

print()
r = subprocess.run(["git", "-C", ROOT, "show", "%s:classes/murasame_class.py" % OLD],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
old_txt = r.stdout or ""
if not old_txt:
    print("!! 备份里没有 classes/murasame_class.py：", (r.stderr or "")[:200])
else:
    old_items = extract(old_txt, "覆盖前（%s）" % OLD)
    print()
    print("=== 差异 ===")
    only_now = [x for x in cur_items if x not in old_items]
    only_old = [x for x in old_items if x not in cur_items]
    print("   只在【现在】有的 %d 个：" % len(only_now))
    for x in only_now[:40]:
        print("      + " + x)
    print("   只在【覆盖前】有的 %d 个：" % len(only_old))
    for x in only_old[:40]:
        print("      - " + x)
