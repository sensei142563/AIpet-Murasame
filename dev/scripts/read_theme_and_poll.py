# -*- coding: utf-8 -*-
"""③ 首页白字：把主题的 colors 全打出来对比（沫子的日常 vs 另一个正常主题）
   ① 关闭桌宠：看 api 那个控制轮询定时器的间隔与实现（判断会不会被卡住）
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"

print("=== ③ 主题 colors 对比 ===")
for theme in ("senrenbanka_copy", "senrenbanka", "senrenbanka2"):
    p = os.path.join(ROOT, "pcl_launcher", "themes", theme, "theme.json")
    if not os.path.isfile(p):
        continue
    try:
        d = json.load(io.open(p, encoding="utf-8", errors="replace"))
    except Exception as e:
        print("   %s ✗ 解析失败 %s" % (theme, e))
        continue
    print("   ── %s（name=%s）" % (theme, d.get("name")))
    c = d.get("colors") or {}
    for k in sorted(c):
        v = c[k]
        print("      %-22s %s" % (k, json.dumps(v, ensure_ascii=False)[:96]))
    bg = d.get("background") or {}
    print("      %-22s %s" % ("background", json.dumps(bg, ensure_ascii=False)[:110]))

print()
print("=== 其他主题列表（看有几个、哪个是默认）===")
td = os.path.join(ROOT, "pcl_launcher", "themes")
for d in sorted(os.listdir(td)):
    pj = os.path.join(td, d, "theme.json")
    nm = ""
    if os.path.isfile(pj):
        try:
            nm = json.load(io.open(pj, encoding="utf-8", errors="replace")).get("name", "")
        except Exception:
            nm = "(解析失败)"
    print("   %-24s %s" % (d, nm))

print()
print("=== ① 控制轮询定时器 ===")
for rel in ("main.py", "classes/murasame_class.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"QTimer|_control_timer|check_flag|check_shutdown|_poll", l) and \
           re.search(r"start\(|setInterval|singleShot|def .*poll|check_shutdown|check_flag", l):
            print("   %-26s %5d| %s" % (rel, i, l.strip()[:104]))
