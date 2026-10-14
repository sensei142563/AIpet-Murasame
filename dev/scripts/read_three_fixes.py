# -*- coding: utf-8 -*-
"""三处关键代码原样打印（准备修）：
  ① classes/murasame_class.py  _14 附近
  ② config.json 的视觉配置 + 视觉请求是怎么拼的
  ③ 「关闭桌宠」链路：main.py 退出段 / api.check_shutdown / 启动器 _send_control
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def show(rel, start, end):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print("   （缺 %s）" % rel)
        return
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    print("   ── %s 第 %d~%d 行 ──" % (rel, start, end))
    for i in range(start - 1, min(len(ls), end)):
        print("   %5d| %s" % (i + 1, ls[i].rstrip()[:116]))


print("=== ① _14 打字错误现场 ===")
show("classes/murasame_class.py", 2900, 2945)

print()
print("=== ② 视觉配置（config.json 相关键）===")
cfg = json.load(io.open(os.path.join(ROOT, "config.json"), encoding="utf-8", errors="replace"))
for k in sorted(cfg):
    if re.search(r"vision|vl|model_name|model_type|api|local_api|cloud", k, re.I):
        v = cfg[k]
        if isinstance(v, dict):
            print("   %-26s %s" % (k, json.dumps(v, ensure_ascii=False)[:150]))
        else:
            print("   %-26s %s" % (k, str(v)[:120]))

print()
print("=== ② 视觉请求是怎么发的 ===")
for rel in ("tool/chat.py", "tool/cloud_api.py", "api.py"):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"vision_model|qwen-vl|vision_source|Model not exist|模型名|model\b.*vl", l):
            print("   %-22s %5d| %s" % (rel, i, l.strip()[:108]))

print()
print("=== ③ 退出链路 ===")
show("main.py", 1094, 1130)
print()
show("pcl_launcher/silicon_window.py", 1543, 1580)
print()
print("   api.py 里的 check_shutdown / 关闭标志：")
p = os.path.join(ROOT, "api.py")
if os.path.isfile(p):
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if re.search(r"shutdown|_shutdown|关闭", l):
            print("   %5d| %s" % (i, l.strip()[:110]))
