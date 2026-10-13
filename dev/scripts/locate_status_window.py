# -*- coding: utf-8 -*-
"""状态窗/状态页：本树 vs 覆盖前备份 vs origin/main 的差异定位。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REFS = (("本树(文件)", None),
        ("origin/main", "remotes/origin/main"),
        ("覆盖前备份", "remotes/origin/backup/main-before-overwrite-20261001"))

KEYS = ("status_page_enabled", "QDialog#statusWindow", "WA_StyledBackground",
        "statusWindow", "状态窗", "她的状态")


def content(ref, path):
    if ref is None:
        p = os.path.join(ROOT, path)
        return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


FILES = ("classes/status_window.py", "config.example.json", "config.json",
         "classes/murasame_class.py", "pcl_launcher/sidebar.py", "pcl_launcher/ui_main.py")

print("=== 逐文件、逐关键字的命中（行数 / 命中）===")
for path in FILES:
    print("--- %s ---" % path)
    for label, ref in REFS:
        t = content(ref, path)
        if not t:
            print("   %-10s （取不到/不存在）" % label)
            continue
        hits = {k: t.count(k) for k in KEYS if k in t}
        print("   %-10s %5d 行   %s" % (label, len(t.split("\n")), hits if hits else "—"))
