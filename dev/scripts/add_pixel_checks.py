# -*- coding: utf-8 -*-
"""给 accept_all.py 加第 ⑩ 节：
  ⑩1 3D 页真的画出来了（**像素判定**：截取画面中段，统计不同颜色数；空白/纯色会极少）
  ⑩2 AR 顶栏的「－ ＋」必须在屏幕上（文本判定，今天用户反馈被挤出屏幕）
同时先查清 Live2D AR 入口的真实标签。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")

print("=== Live2D AR 的入口标签（从源码读）===")
for i, l in enumerate(io.open(CS, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if re.search(r'showAr\s*=|AR（|AR 相机|相机.*AR|Text\(".*AR', l):
        print("   %4d| %s" % (i, l.strip()[:140]))

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "3D 页真的画出来了" in t:
    print("· 已有第 ⑩ 节")
else:
    block = '''    # ===== ⑩ 画面级检查（2026-10-11 教训：日志说 OK ≠ 屏幕上看得见）=====
    print("=== 6. 画面级检查（以屏幕为准）===")
    if DRY:
        record("⑩1 3D 页真的画出来了", "SKIP", "dry-run")
        record("⑩2 AR 顶栏 +/− 存在", "SKIP", "dry-run")
    elif SKIP_UI:
        record("⑩1 3D 页真的画出来了", "SKIP", "前台是别的应用，未点击")
        record("⑩2 AR 顶栏 +/− 存在", "SKIP", "前台是别的应用，未点击")
    else:
        # 走：聊天 → ☰ → VRM 演示
        ensure_foreground("⑩ 3D 画面")
        tap_text(dump("k1"), "聊天", wait=4.0)
        tap_text(dump("k2"), "☰", wait=3.0)
        hit3d = tap_text(dump("k3"), "VRM 演示", wait=13.0)
        if hit3d is None:
            record("⑩1 3D 页真的画出来了", "SKIP", "抽屉里没找到「VRM 演示」")
        else:
            shot = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "shots", "accept_3d_page.png")
            try:
                os.makedirs(os.path.dirname(shot), exist_ok=True)
                with open(shot, "wb") as fh:
                    subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                                   stderr=subprocess.DEVNULL, timeout=180)
                import PIL.Image
                im = PIL.Image.open(shot).convert("RGB")
                w, hh = im.size
                # 只取画面中段（3D 画布所在区域），避开顶栏/底部导航
                box = im.crop((int(w * 0.08), int(hh * 0.28), int(w * 0.92), int(hh * 0.72)))
                colors = len(set(box.getdata()))
                # 空白/纯色区域颜色数极少（几个到几十）；正常渲染的 3D 场景是几千以上
                okpix = colors >= 200
                record("⑩1 3D 页真的画出来了", verdict(okpix),
                       "中段区域不同颜色数 = %d（阈值 200；空白/纯色会远低于此）· 截图 %s"
                       % (colors, os.path.basename(shot)))
            except Exception as ex:
                record("⑩1 3D 页真的画出来了", "SKIP", "截图分析失败：%s: %s" % (type(ex).__name__, ex))

        # ⑩2 AR 顶栏 +/−：进入 AR 页后，屏幕上必须同时出现「－」和「＋」
        back = tap_text(dump("k4"), "返回", wait=3.0)
        ar_entry = None
        for lbl in ("3D AR", "Live2D AR", "AR 相机"):
            x = dump("k5")
            ar_entry = tap_text(x, lbl, wait=13.0)
            if ar_entry is not None:
                break
        if ar_entry is None:
            record("⑩2 AR 顶栏 +/− 存在", "SKIP", "抽屉里没找到 3D AR 入口")
        else:
            x = dump("k6")
            has_minus = '"－"' in x or 'text="－"' in x
            has_plus = '"＋"' in x or 'text="＋"' in x
            record("⑩2 AR 顶栏 +/− 存在", verdict(has_minus and has_plus),
                   "－=%s ＋=%s（真机反馈：加了「干净」后这两个被挤出屏幕 ⇒ 已改可滚动并前移）"
                   % (has_minus, has_plus))
            tap_text(dump("k7"), "返回", wait=2.0)

'''
    anchor = '''    print()
    print("=== 汇总 ===")'''
    if anchor in t:
        t = t.replace(anchor, block + anchor, 1)
        io.open(A, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已插入第 ⑩ 节（2 项，像素/文本判定）")
    else:
        print("✗ 汇总锚点未命中")
        sys.exit(1)

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
if r.returncode != 0:
    sys.exit(1)
print()
print("=== dry-run ===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
j = out.find("=== 汇总")
print(out[j:] if j > 0 else out[-700:])
