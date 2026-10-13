# -*- coding: utf-8 -*-
"""顺手修 pets/murasame/avatar.png（其实是 JPEG）：
   原文件另存为 avatar.jpg 保留，再把 avatar.png 写成**真正的 PNG**
   ⇒ pet.json 里的 "avatar": "avatar.png" 不用改，Qt 不依赖 JPEG 插件也不会再"头像没了"。
   顺带扫一遍所有角色：pet.json 声明的头像文件，扩展名与真实格式是否一致。
"""
import io
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
PETS = os.path.join(ROOT, "pets")


def kind(p):
    try:
        with open(p, "rb") as f:
            b = f.read(12)
    except Exception:
        return "读不到"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if b[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "WEBP"
    return "?"


print("=== ① 修之前：所有角色的头像格式 ===")
targets = []
for d in sorted(os.listdir(PETS)):
    pj = os.path.join(PETS, d, "pet.json")
    if not os.path.isfile(pj):
        continue
    t = io.open(pj, encoding="utf-8", errors="replace").read()
    m = re.search(r'"avatar"\s*:\s*"([^"]+)"', t)
    if not m:
        print("   %-12s （pet.json 没写 avatar）" % d)
        continue
    av = m.group(1)
    fp = os.path.join(PETS, d, av.replace("/", os.sep))
    k = kind(fp) if os.path.isfile(fp) else "文件不存在"
    exp = os.path.splitext(av)[1].lower().lstrip(".")
    flag = ""
    if k != "文件不存在":
        if exp == "png" and k != "PNG":
            flag = "  ← ✗ 扩展名是 png 但内容是 %s" % k
            targets.append((d, fp, k))
        elif exp in ("jpg", "jpeg") and k != "JPEG":
            flag = "  ← ✗ 扩展名是 jpg 但内容是 %s" % k
    print("   %-12s %-24s %-12s%s" % (d, av, k, flag))

print()
print("=== ② 逐个修（保留原图为同目录的 .jpg 副本，再写真正的 PNG）===")
try:
    from PIL import Image
except Exception as e:
    print("   ✗ 没有 Pillow：", e)
    sys.exit(1)

for d, fp, k in targets:
    try:
        base, _ = os.path.splitext(fp)
        keep = base + (".jpg" if k == "JPEG" else "." + k.lower())
        if not os.path.isfile(keep):
            shutil.copy2(fp, keep)
            print("   ✓ 原图已保留为 %s" % os.path.basename(keep))
        im = Image.open(fp)
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        im.save(fp, "PNG")
        print("   ✓ %s/%s 已改写为真 PNG（%d 字节，原 %s）"
              % (d, os.path.basename(fp), os.path.getsize(fp), k))
    except Exception as e:
        print("   ✗ %s/%s 失败：%s" % (d, os.path.basename(fp), e))

print()
print("=== ③ 修之后复查 ===")
for d in sorted(os.listdir(PETS)):
    pj = os.path.join(PETS, d, "pet.json")
    if not os.path.isfile(pj):
        continue
    t = io.open(pj, encoding="utf-8", errors="replace").read()
    m = re.search(r'"avatar"\s*:\s*"([^"]+)"', t)
    if not m:
        continue
    av = m.group(1)
    fp = os.path.join(PETS, d, av.replace("/", os.sep))
    k = kind(fp) if os.path.isfile(fp) else "文件不存在"
    exp = os.path.splitext(av)[1].lower().lstrip(".")
    ok = (k == "文件不存在" or (exp == "png" and k == "PNG")
          or (exp in ("jpg", "jpeg") and k == "JPEG"))
    print("   %-12s %-24s %-10s %s" % (d, av, k, "✓" if ok else "✗ 仍不匹配"))
