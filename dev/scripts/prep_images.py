# -*- coding: utf-8 -*-
"""① 把选定素材按用途规范命名，放进 E:\\university\\order\\ppt-assets\\shots\\
   ② 写 dev/scripts/ppt_add_images.py：按映射把图贴到 Deck.pptx 的指定页
      （写在脚本层，**不动 E:\\Codex\\workflows\\ppt 的引擎文件**）
解析：本机屏幕缩放 125%，幻灯片默认 13.333in x 7.5in
"""
import io
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SRC = r"E:\university\order\python\pet\新建文件夹"
SHOTS = r"E:\university\order\ppt-assets\shots"

# 映射：源文件 → 规范名 → 用途
PICK = [
    ("屏幕截图 2026-10-14 154101.png", "S1-cover.png", "封面：她在桌面上（深色服装）"),
    ("屏幕截图 2026-10-14 154235.png", "S2-menu.png", "右键完整菜单"),
    ("屏幕截图 2026-10-14 154334.png", "S3a-outfit.png", "换装：浅色和服"),
    ("屏幕截图 2026-10-14 154418.png", "S3b-outfit.png", "换装：另一套"),
    ("2aec0f9f8652c9635552f3cbe4ad311d.jpg", "S4a-chat.png", "聊天（手机）"),
    ("7512802f7d68578c9750df0243470748.jpg", "S4b-chat.png", "聊天（群里发图）"),
    ("ff0a9739827b27c12d9e012d0090d6b4.jpg", "S4c-chat.png", "聊天（对话）"),
    ("屏幕截图 2026-10-14 003718.png", "S5-status.png", "启动器状态页（五个页签）"),
    ("屏幕截图 2026-10-14 003708.png", "S5b-memory.png", "启动器记忆页"),
    ("屏幕截图 2026-10-14 154603.png", "S6-launcher.png", "启动器总览 + 模型状态"),
    ("屏幕截图 2026-10-14 003639.png", "S6b-plugins.png", "启动器插件页"),
    ("屏幕截图 2026-10-14 003622.png", "S7-settings.png", "设置页：语音/识别开关"),
    ("屏幕截图 2026-10-14 003646.png", "S7b-settings.png", "设置页：另一块"),
    ("3c84b819abe37ea1c5e053d36ecee343.jpg", "S9-phone-home.jpg", "手机主页"),
    ("6ef6abf873a5a155fc4a9e7a64c5ff1a.jpg", "S11-ar1.jpg", "AR/3D 实景 ①"),
    ("d1f46c5e55dfadc39ccfdcc945ace089.jpg", "S11-ar2.jpg", "AR/3D 实景 ②"),
    ("e2fe7f45dcba282cc1e80a882b0414e8.jpg", "S10b-im-list.jpg", "IM 会话列表"),
    ("屏幕截图 2026-10-14 003652.png", "S12-changelog.png", "更新日志（备用）"),
]

print("=== ① 规范命名并拷入 shots\\ ===")
os.makedirs(SHOTS, exist_ok=True)
done = []
for src_name, dst_name, why in PICK:
    sp = os.path.join(SRC, src_name)
    dp = os.path.join(SHOTS, dst_name)
    if not os.path.isfile(sp):
        print("   ✗ 缺源文件: %s" % src_name)
        continue
    shutil.copy2(sp, dp)
    done.append((dst_name, why))
    print("   ✓ %-22s ← %-34s （%s）" % (dst_name, src_name[:34], why))
print("   共 %d 个" % len(done))

# ---------- ② 生成贴图脚本 ----------
ADD_IMG = '''# -*- coding: utf-8 -*-
"""按映射把截图贴到 Deck.pptx 的指定页。

⚠ 写在脚本层：**不动 E:\\Codex\\workflows\\ppt 的引擎文件**。
   用法：python dev/scripts/ppt_add_images.py [目标.pptx]
   默认目标 dev/ppt/out/Deck.pptx；页号是 1-based（与讲稿、操作单一致）。

版式规则（幻灯片 13.333in × 7.5in）：
  · 文字在上半部分，所以图片一律放**下半区**（y 从 4.30in 到 7.25in，居中）；
  · 同一页多张图**等高并排**、间距 0.18in；
  · 竖图（手机截图）自动按高度缩放；横图同理，都不会超出可用宽度。
"""
import io
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Emu

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")
SHOTS = r"E:\\university\\order\\ppt-assets\\shots"

# 页号 → [图片文件名...]（按从左到右顺序）
#   页码对应 24 页版：1 封面 / 13 她现在能做的事 / 14 形象与语音 / 15 记忆与陪伴 /
#                    16 出桌面·上手机 / 17 工程质量 / 19 近期 / 20 互动 / 22 远期
PLAN = {
    1:  ["S1-cover.png"],
    13: ["S2-menu.png", "S4b-chat.png"],
    14: ["S3a-outfit.png", "S3b-outfit.png"],
    15: ["S5-status.png", "S5b-memory.png"],
    16: ["S6-launcher.png", "S9-phone-home.jpg", "S10b-im-list.jpg"],
    17: ["S8-tests.png"],                     # 若还没生成，脚本会自动跳过
    19: ["S9-phone-home.jpg", "S11-ar1.jpg"],
    20: ["S11-ar2.jpg"],
    22: ["S11-ar1.jpg"],
}

TOP_IN, BOTTOM_IN = 4.30, 7.25
GAP_IN = 0.18
SLIDE_W, SLIDE_H = 13.333, 7.5
MAX_W = SLIDE_W - 1.2          # 左右各留 0.6in


def add_row(slide, paths):
    """把若干张图等高并排，居中放在下半区。返回放置的张数。"""
    from PIL import Image
    usable_h = BOTTOM_IN - TOP_IN
    ims = []
    for p in paths:
        if not os.path.isfile(p):
            print("      ⚠ 跳过（没有这张）: %s" % os.path.basename(p))
            continue
        try:
            im = Image.open(p)
            ims.append((p, im.width, im.height))
        except Exception as e:
            print("      ⚠ 打不开 %s: %s" % (os.path.basename(p), e))
    if not ims:
        return 0
    # 缩小高度直到总宽放得下
    h = usable_h
    for _ in range(60):
        total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
        if total_w <= MAX_W:
            break
        h -= 0.05
    total_w = sum(h * (w / hh) for _, w, hh in ims) + GAP_IN * (len(ims) - 1)
    x = (SLIDE_W - total_w) / 2.0
    y = TOP_IN + (usable_h - h) / 2.0
    for p, w, hh in ims:
        ww = h * (w / hh)
        slide.shapes.add_picture(p, Inches(x), Inches(y), width=Inches(ww), height=Inches(h))
        x += ww + GAP_IN
    return len(ims)


prs = Presentation(DECK)
slides = list(prs.slides)
print("   目标：%s（%d 页）" % (os.path.basename(DECK), len(slides)))
n = 0
for page, names in sorted(PLAN.items()):
    if page > len(slides):
        print("   ⚠ 第 %d 页不存在，跳过" % page)
        continue
    paths = [os.path.join(SHOTS, nm) for nm in names]
    k = add_row(slides[page - 1], paths)
    if k:
        print("   ✓ 第 %2d 页贴了 %d 张：%s" % (page, k, "、".join(names[:k])))
        n += k
prs.save(DECK)
print("   共贴入 %d 张 → %s" % (n, DECK))
'''
p = os.path.join(ROOT, "dev", "scripts", "ppt_add_images.py")
io.open(p, "w", encoding="utf-8", newline="\n").write(ADD_IMG)
print()
print("✓ ② 已写 dev/scripts/ppt_add_images.py")
print("   映射：第 1 / 13 / 14 / 15 / 16 / 17 / 19 / 20 / 22 页")
