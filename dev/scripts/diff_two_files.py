# -*- coding: utf-8 -*-
"""打印 colors.py 与 natsume/pet.json 相对备份的差异（限长），判断能否整file/整键恢复。"""
import io
import os
import subprocess
import sys
import difflib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"


def show(ref, path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


def cur(path):
    p = os.path.join(ROOT, path)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


for path in ("pcl_launcher/colors.py", "pets/natsume/pet.json"):
    a = cur(path)
    b = show(REF_BAK, path)
    print("=" * 76)
    print("=== %s ===" % path)
    print("   当前 %d 行 / 备份 %d 行" % (len(a.split("\n")), len(b.split("\n"))))
    d = list(difflib.unified_diff(a.split("\n"), b.split("\n"), "当前树", "覆盖前备份",
                                  lineterm="", n=2))
    if not d:
        print("   （完全相同）")
    else:
        print("   差异 %d 行（下面显示前 60 行差异，+ 表示备份里有、- 表示当前树独有）" % len(d))
        for l in d[:60]:
            print("   " + l[:140])
    print()
