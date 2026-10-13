# -*- coding: utf-8 -*-
"""① 把 6 套候选模板的 preview.png 拼成一张对照图（带编号和名字），供用户挑选
   ② 检查 GordenPPTSkill 在本机能不能跑：python-pptx / LibreOffice / pdftoppm / build_pptx.py --help
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SKILL = r"E:\Codex\skills\GordenPPTSkill"
OUT = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\ppt\out\template-candidates.png"

CAND = [
    ("architecture-deck", "技术架构（深蓝）— 功能/实现方法"),
    ("top-thesis", "学术酒红 — 开题/答辩版"),
    ("mckinsey-style", "麦肯锡风（酱红+深蓝灰）— 调研对比/讲故事"),
    ("competition-speech", "竞聘述职（深蓝+砖红）— 汇报/复盘"),
    ("minimal-business-summary", "简约商务（深蓝白）— 干净短汇报"),
    ("data-viz-deck", "数据可视化（深蓝+砖红）— 图表多"),
]

# ---------- ① 工具链检查 ----------
print("=== ① 工具链检查 ===")
try:
    import pptx  # noqa: F401
    print("   python-pptx:", getattr(pptx, "__version__", "?"), "✓")
except Exception as e:
    print("   python-pptx: ✗", e)

for exe in ("soffice", "libreoffice", "pdftoppm", "python3"):
    r = subprocess.run(["where", exe], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print("   %-12s %s" % (exe, (r.stdout or "").strip().split("\n")[0] if r.returncode == 0 else "✗ 不在 PATH"))

print()
print("=== ② build_pptx.py --help（能不能直接被调用）===")
bp = os.path.join(SKILL, "scripts", "build_pptx.py")
if os.path.isfile(bp):
    r = subprocess.run([sys.executable, bp, "--help"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    print("   退出码 =", r.returncode)
    for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[:14]:
        print("   |", l[:104])
else:
    print("   ✗ 没找到", bp)

# ---------- ③ 拼对照图 ----------
print()
print("=== ③ 拼候选对照图 ===")
try:
    from PIL import Image, ImageDraw
except Exception as e:
    print("   ✗ 没有 Pillow:", e)
    sys.exit(0)

tiles = []
for slug, desc in CAND:
    p = os.path.join(SKILL, "templates", slug, "preview.png")
    if not os.path.isfile(p):
        print("   ⚠ 缺预览:", slug)
        continue
    im = Image.open(p).convert("RGB")
    # 缩到统一宽度
    W = 620
    im = im.resize((W, max(1, int(im.height * W / im.width))), Image.LANCZOS)
    tiles.append((slug, desc, im))
    print("   ✓ %-26s %dx%d" % (slug, im.width, im.height))

if tiles:
    pad, label_h = 16, 52
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    tw = max(t[2].width for t in tiles)
    th = max(t[2].height for t in tiles)
    W = cols * tw + (cols + 1) * pad
    H = rows * (th + label_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (W, H), (245, 245, 248))
    d = ImageDraw.Draw(sheet)
    for i, (slug, desc, im) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + label_h + pad)
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + tw - 1, y + im.height - 1], outline=(180, 180, 190))
        d.text((x + 4, y + im.height + 6), "%d) %s" % (i + 1, slug), fill=(20, 20, 30))
        d.text((x + 4, y + im.height + 26), desc, fill=(90, 90, 105))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sheet.save(OUT)
    print("   ✓ 已保存:", OUT, "(%dx%d)" % (sheet.width, sheet.height))
