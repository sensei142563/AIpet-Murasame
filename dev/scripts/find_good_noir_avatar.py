# -*- coding: utf-8 -*-
"""从 git 历史里找一张"好的"诺瓦头像：
  ① 列出 pets/noir 下头像相关文件的全部历史版本（commit + blob）
  ② 把每个版本导出成图片
  ③ 拼成对照表（含"看起来像噪点"的自动判断），供目视挑出好的那张
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image, ImageDraw

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TMP = os.path.join(ROOT, "dev", "tmp", "noir_avatar_hist")
OUT = os.path.join(ROOT, "dev", "ppt", "out", "noir-avatar-history.png")
os.makedirs(TMP, exist_ok=True)


def sh(args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


PATHS = ["pets/noir/avatar.jpg", "pets/noir/avatar.png", "pets/noir/诺瓦.jpg"]
rows = []
for rel in PATHS:
    out = sh(["git", "log", "--all", "--format=%H|%ad|%s", "--date=short", "--", rel])
    for line in out.split("\n"):
        if not line.strip():
            continue
        h, date, subj = (line.split("|", 2) + ["", ""])[:3]
        # 取该提交下这个文件的内容
        c = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (h, rel)],
                           capture_output=True)
        blob = c.stdout
        if not blob:
            continue
        ext = os.path.splitext(rel)[1]
        fp = os.path.join(TMP, "%s_%s%s" % (h[:8], os.path.basename(rel).replace(".", "_"), ext))
        with open(fp, "wb") as f:
            f.write(blob)
        rows.append((h[:8], date, rel, len(blob), fp, subj[:44]))

print("=== 历史版本（共 %d 个）===" % len(rows))
for h, date, rel, sz, fp, subj in rows:
    print("   %s %s %-22s %8d B  %s" % (h, date, rel, sz, subj))


def noise_score(fp):
    """粗略判断：邻域差分过大 + 颜色数量异常多 ⇒ 像噪点。"""
    try:
        im = Image.open(fp).convert("RGB").resize((64, 64))
        px = list(im.getdata())
        diff = n = 0
        for y in range(63):
            for x in range(63):
                a = px[y * 64 + x]
                b = px[y * 64 + x + 1]
                diff += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
                n += 1
        avg = diff / max(1, n)
        cols = len(set(px))
        return avg, cols
    except Exception:
        return 999, 0


print()
print("=== 逐张评分（avg邻差 越大越像噪点；颜色数 越多越像噪点）===")
scored = []
for h, date, rel, sz, fp, subj in rows:
    a, c = noise_score(fp)
    scored.append((a, c, h, date, rel, sz, fp, subj))
    print("   %s %s %-22s avg=%6.1f 色数=%5d  %s" % (h, date, rel, a, c,
                                                   "⚠ 像噪点" if a > 70 else ""))

# 拼图：每行一张
if scored:
    CELL, PAD, LAB = 200, 10, 34
    cols = 5
    rowsn = (len(scored) + cols - 1) // cols
    W = cols * CELL + (cols + 1) * PAD
    H = rowsn * (CELL + LAB) + (rowsn + 1) * PAD
    sheet = Image.new("RGB", (W, H), (246, 246, 249))
    d = ImageDraw.Draw(sheet)
    for i, (a, c, h, date, rel, sz, fp, subj) in enumerate(scored):
        r, cc = divmod(i, cols)
        x = PAD + cc * (CELL + PAD)
        y = PAD + r * (CELL + LAB + PAD)
        d.rectangle([x, y, x + CELL - 1, y + CELL - 1], fill=(255, 255, 255),
                    outline=(190, 190, 200))
        try:
            im = Image.open(fp).convert("RGBA")
            im.thumbnail((CELL - 8, CELL - 8), Image.LANCZOS)
            sheet.paste(im, (x + (CELL - im.width) // 2, y + (CELL - im.height) // 2), im)
        except Exception as e:
            d.text((x + 6, y + 6), "打不开 %s" % str(e)[:20], fill=(200, 40, 40))
        d.text((x + 3, y + CELL + 4), "%s %s" % (h, date), fill=(20, 20, 30))
        d.text((x + 3, y + CELL + 18), "%s avg=%.0f" % (os.path.basename(rel)[:16], a),
               fill=(110, 110, 125))
    sheet.save(OUT)
    print()
    print("   ✓ 对照表：%s (%dx%d)" % (OUT, sheet.width, sheet.height))
