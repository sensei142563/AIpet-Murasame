# -*- coding: utf-8 -*-
"""修诺瓦头像：把坏掉的 avatar.png 换回"从原 JPEG 正确转出"的 PNG。
   关键：这次要**看图验收**（上次只看文件头就下结论，错了）。
"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image

ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
ND = os.path.join(ROOT, "pets", "noir")
OUT = os.path.join(ROOT, "dev", "ppt", "out")

bad = os.path.join(ND, "avatar.png")       # 现在这个：是 PNG 头，但图像是噪点
jpg = os.path.join(ND, "avatar.jpg")       # 协作者保留的原图
jpg2 = os.path.join(ND, "诺瓦.jpg")

print("=== ① 现状 ===")
for p in (bad, jpg, jpg2):
    if os.path.isfile(p):
        im = Image.open(p)
        print("   %-18s %8d B  %s %sx%s" % (os.path.basename(p), os.path.getsize(p),
                                            im.mode, im.width, im.height))
    else:
        print("   %-18s （不存在）" % os.path.basename(p))

# 先存三张预览，供之后目视对比
def prev(src, name, size=(180, 180)):
    im = Image.open(src).convert("RGBA")
    im.thumbnail(size, Image.LANCZOS)
    p = os.path.join(OUT, name)
    im.save(p)
    return p

pv_bad = prev(bad, "avatar-noir-BAD.png") if os.path.isfile(bad) else None
pv_jpg = prev(jpg, "avatar-noir-src-jpg.png") if os.path.isfile(jpg) else None
print("   预览：", os.path.basename(pv_bad or "-"), "/", os.path.basename(pv_jpg or "-"))

print()
print("=== ② 从原 JPEG 正确转出 PNG（同名覆盖，pet.json 不用改）===")
src = jpg if os.path.isfile(jpg) else jpg2
if not os.path.isfile(src):
    print("   ✗ 找不到原图，退出")
    sys.exit(1)
print("   源：", os.path.basename(src), os.path.getsize(src), "B")
# 备份坏文件（以防万一）
bak = bad + ".broken.bak"
if os.path.isfile(bad) and not os.path.isfile(bak):
    shutil.copy2(bad, bak)
    print("   （坏文件已备份为 %s）" % os.path.basename(bak))
im = Image.open(src)
im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
im.save(bad, "PNG")
print("   ✓ 已写入 %s  %d B  %sx%s" % (os.path.basename(bad), os.path.getsize(bad),
                                       im.width, im.height))
pv_new = prev(bad, "avatar-noir-NEW.png")
print("   预览：", os.path.basename(pv_new))

print()
print("=== ③ 顺手核对其他角色的头像内容是否也正常（不是噪点）===")
import statistics  # noqa: E402
pets = os.path.join(ROOT, "pets")
import io  # noqa: E402
import re  # noqa: E402
for d in sorted(os.listdir(pets)):
    pj = os.path.join(pets, d, "pet.json")
    if not os.path.isfile(pj):
        continue
    t = io.open(pj, encoding="utf-8", errors="replace").read()
    m = re.search(r'"avatar"\s*:\s*"([^"]+)"', t)
    if not m:
        continue
    fp = os.path.join(pets, d, m.group(1).replace("/", os.sep))
    if not os.path.isfile(fp):
        print("   %-12s ✗ 文件不存在" % d)
        continue
    try:
        im = Image.open(fp).convert("RGB")
        small = im.resize((48, 48))
        px = list(small.getdata())
        # 噪点特征：相邻像素差异极大（平均绝对差很高）
        diff = 0
        n = 0
        for y in range(47):
            for x in range(47):
                a = px[y * 48 + x]
                b = px[y * 48 + x + 1]
                diff += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
                n += 1
        avg = diff / max(1, n)
        flag = "  ← ⚠ 像噪点" if avg > 60 else ""
        print("   %-12s avg邻差=%5.1f %s" % (d, avg, flag))
    except Exception as e:
        print("   %-12s ✗ 打不开：%s" % (d, e))
