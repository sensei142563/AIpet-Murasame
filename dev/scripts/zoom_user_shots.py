# -*- coding: utf-8 -*-
"""把用户发的两张截图局部放大，看清：
  图1：顶部按钮行（要挪走的两个预载按钮）+ 底部「模型状态」
  图2：我的桌宠卡片 / 全部桌宠详情里的头像（"乱码"到底指哪）
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image

ATT = r"C:\Users\ASUS\.dsh\attachments\v1\objects"
S1 = os.path.join(ATT, "a2", "a2c4aab845adefb3319ef30666dcde21daa1e3c7b65305c129b914487b7db3d8")
S2 = os.path.join(ATT, "4c", "4c6acf2f499bf88b665d2afccf39d53850253ecaf0ce61a21a8d2d67c02ad747")
OUT = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\ppt\out"

for p in (S1, S2):
    print("   %s  存在=%s" % (os.path.basename(p), os.path.isfile(p)))
    if os.path.isfile(p):
        im = Image.open(p)
        print("      尺寸 %dx%d  %s" % (im.width, im.height, im.mode))


def crop(src, box, name, scale=2):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = [int(v * (w if i % 2 == 0 else h)) for i, v in enumerate(box)]
    c = im.crop((x0, y0, x1, y1))
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    out = os.path.join(OUT, name)
    c.save(out)
    print("   ✓ %s  (%dx%d)" % (name, c.width, c.height))
    return out


print()
print("=== 图1 局部 ===")
# 顶部按钮行（相对坐标）
crop(S1, (0.17, 0.16, 0.98, 0.26), "zoom1-top-buttons.png")
# 「桌宠控制面板」+「快捷工具」（要把按钮挪进来的地方）
crop(S1, (0.17, 0.28, 0.98, 0.62), "zoom1-panels.png")
# 底部「模型状态」
crop(S1, (0.17, 0.63, 0.98, 0.82), "zoom1-model-status.png")

print()
print("=== 图2 局部 ===")
# 「我的桌宠」卡片行
crop(S2, (0.15, 0.36, 0.60, 0.50), "zoom2-my-pets.png", 3)
# 「全部桌宠」详情（第一个卡片）
crop(S2, (0.15, 0.56, 0.98, 0.74), "zoom2-detail1.png", 2)
# 第二个卡片
crop(S2, (0.15, 0.74, 0.98, 0.92), "zoom2-detail2.png", 2)
