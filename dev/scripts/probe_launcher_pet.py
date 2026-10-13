# -*- coding: utf-8 -*-
"""找启动器里"当前角色"的存取方式，以及选中角色时的回调（供按钮实时显示角色名）。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\university\order\python\pet\AIpet-Murasame-main\pcl_launcher\silicon_window.py"
t = io.open(P, encoding="utf-8", errors="replace").read().split("\n")

PAT = re.compile(r"current_pet|active_pet|selected_pet|_cur_pet|pet_id|display_name"
                 r"|set_current|当前角色|_select_pet|on_pet|pet_registry|active\(")
print("=== 相关行 ===")
n = 0
for i, l in enumerate(t, 1):
    if PAT.search(l):
        print("   %5d| %s" % (i, l.rstrip()[:116]))
        n += 1
        if n >= 30:
            print("   …（截断）")
            break

print()
print("=== 预载按钮那一整段（852-876）===")
for i in range(851, 876):
    if i < len(t):
        print("   %5d| %s" % (i + 1, t[i].rstrip()[:116]))

print()
print("=== preload_tts 开头（1142-1170）===")
for i in range(1141, 1170):
    if i < len(t):
        print("   %5d| %s" % (i + 1, t[i].rstrip()[:116]))
