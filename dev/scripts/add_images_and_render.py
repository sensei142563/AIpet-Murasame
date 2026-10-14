# -*- coding: utf-8 -*-
"""① 备份 Deck.pptx（保留纯文字版）
   ② 用**真实测试输出**生成 S8-tests.png（终端风格；内容是真的，只是由我渲染 —— 会告知用户）
   ③ 跑 ppt_add_images.py 贴图
   ④ 渲染 24 页 PNG，供目视验收
"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SHOTS = r"E:\university\order\ppt-assets\shots"
DECK = os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① 备份 ===")
bak = os.path.join(ROOT, "dev", "ppt", "out", "Deck-文字版.pptx")
if os.path.isfile(DECK):
    shutil.copy2(DECK, bak)
    print("   ✓ 备份为 %s（纯文字版，随时可回退）" % os.path.basename(bak))

print()
print("=== ② 用真实测试输出生成 S8-tests.png ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=ENV, timeout=1800)
out = ((r.stdout or "") + (r.stderr or ""))
tail = [l for l in out.split("\n") if l.strip()][-12:]
print("   测试退出码 = %d，末尾 %d 行：" % (r.returncode, len(tail)))
for l in tail:
    print("      " + l.strip()[:118])

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
W, H = 1400, 560
img = Image.new("RGB", (W, H), (18, 18, 22))
dr = ImageDraw.Draw(img)
# 终端标题栏
dr.rectangle([0, 0, W, 46], fill=(38, 38, 46))
def _font(size, mono=True):
    cands = ([r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\lucon.ttf"] if mono
             else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"])
    for c in cands:
        if os.path.isfile(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()

f_title = _font(20, False)
f_body = _font(19)
dr.text((16, 12), "AIpet 自检 · tests\\run_all.py", font=f_title, fill=(220, 220, 230))
# 正文：把真实输出画上去
y = 64
for l in tail:
    s = l.rstrip()
    color = (235, 235, 240)
    if "总计" in s or "全部通过" in s:
        color = (120, 230, 140)
    elif "failed" in s.lower() or "失败" in s and "0 个文件失败" not in s:
        color = (240, 140, 120)
    if "-----" in s:
        color = (90, 90, 105)
    dr.text((16, y), s[:130], font=f_body, fill=color)
    y += 30
    if y > H - 34:
        break
dr.text((16, H - 30), "（本图由真实运行输出渲染：内容未改，仅做了终端配色）",
        font=_font(15, False), fill=(120, 120, 135))
p8 = os.path.join(SHOTS, "S8-tests.png")
img.save(p8)
print("   ✓ 已生成 %s (%dx%d)" % (p8, W, H))

print()
print("=== ③ 贴图（不动引擎文件）===")
r2 = subprocess.run([sys.executable, os.path.join(ROOT, "dev", "scripts", "ppt_add_images.py"),
                     DECK], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=ENV, timeout=900)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if l.strip():
        print("   " + l.strip()[:130])

print()
print("=== ④ 渲染 24 页做验收 ===")
r3 = subprocess.run(["powershell", "-NoProfile", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1", "-Deck", DECK],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=2400)
for l in ((r3.stdout or "") + (r3.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:120])
