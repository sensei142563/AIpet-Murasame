# -*- coding: utf-8 -*-
"""重建 deck（数字已同步 389）→ 挂讲稿 → 渲染 → 提交。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
env = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① 重建 ===")
r = subprocess.run([sys.executable, r"E:\Codex\workflows\ppt\scripts\build_deck.py",
                    "--outline", "dev\\ppt\\outline.json", "--out", "dev\\ppt\\out\\Deck.pptx",
                    "--theme", "dev\\ppt\\theme-murasame.json"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=1200)
print("   build 退出码 =", r.returncode)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if l.strip() and ("已生成" in l or "Error" in l or "Permission" in l):
        print("   " + l.strip()[:110])
if r.returncode != 0:
    print("   ✗ 构建失败：Deck.pptx 可能还被 WPS 占着")
    sys.exit(1)

r2 = subprocess.run([sys.executable, os.path.join(ROOT, "dev", "scripts", "ppt_add_notes.py")],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env, timeout=1200)
for l in ((r2.stdout or "") + (r2.stderr or "")).split("\n"):
    if "缺备注" in l or "已写入备注" in l:
        print("   " + l.strip()[:110])

r3 = subprocess.run(["powershell", "-NoProfile", "-File",
                     r"E:\Codex\workflows\ppt\scripts\render_qc.ps1",
                     "-Deck", os.path.join(ROOT, "dev", "ppt", "out", "Deck.pptx")],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400)
for l in ((r3.stdout or "") + (r3.stderr or "")).split("\n"):
    if "Rendered" in l or "PDF" in l:
        print("   " + l.strip()[:110])

print()
print("=== ② 复核 pptx 里的数字 ===")
r4 = subprocess.run([sys.executable, "-c",
                     "from pptx import Presentation\n"
                     "p=Presentation(r'dev/ppt/out/Deck.pptx')\n"
                     "n=len(p.slides._sldIdLst)\n"
                     "hit=[(i,l) for i,s in enumerate(p.slides,1) for sh in s.shapes "
                     "if sh.has_text_frame for l in sh.text_frame.text.split(chr(10)) "
                     "if '389' in l or '386' in l]\n"
                     "print('   页数:', n)\n"
                     "for i,l in hit: print('   第 %d 页: %s' % (i, l.strip()[:70]))\n"],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env, timeout=600)
print((r4.stdout or "") + (r4.stderr or ""))

MSG = """docs: 自检项数 386 → 389（恢复主题后 test_frontend_style 涨了 3 项）并重建 deck

## 为什么会变
`tests/test_frontend_style.py` 是**按主题资源内容**计数的（31 项）。本轮恢复「沫子的日常」主题、
补齐 9 个资源后，它 +3 项 ⇒ 总计 **389**。
各项明细：bounds 68 / bugfix_0930 67 / bugfix_0930b 108 / config_contracts 39 /
frontend_style 31 / plugin_markup 19 / qt_lifecycle 30 / vision_interface 27（另两个 0 项）。

## 同步的地方（8 个文件）
README、（PPT）outline+notes、录屏操作单、本地视觉口径排查、大厂入局与对标补查、
docs/plan 两份（它们此前已带"2026-10-13 更正"标注）—— 全部 386 → 389。

## 重建
build_deck → ppt_add_notes（重建会丢备注）→ render_qc 渲染 24 页 → 读回 pptx 复核数字。

## 记一笔（设计观察，不属本次改动）
`test_frontend_style.py` 的项数**随内容变化** ⇒ 文档里写死的数字会**反复过期**。
更稳的做法是让该体检输出"稳定项数"（把随内容增减的检查合并计一条），
或者文档里只写"全绿"、不写具体数字。本轮先按现状同步，**留作待办**。
"""
p = os.path.join(MAP, "_msg_389.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("=== ③ 提交 ===")
print("   桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("   未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
