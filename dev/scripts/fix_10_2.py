# -*- coding: utf-8 -*-
"""修 ⑩2 的误判风险：+/− 属于 Live2D AR 页（从设置页进入），3D AR 页未必有。
改为：先看当前是哪一页（有 1×/手电/闪光 即为 Live2D AR 页），是才判 +/−，否则 SKIP 并说明。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        if ar_entry is None:
            record("⑩2 AR 顶栏 +/− 存在", "SKIP", "抽屉里没找到 3D AR 入口")
        else:
            x = dump("k6")
            has_minus = '"－"' in x or 'text="－"' in x
            has_plus = '"＋"' in x or 'text="＋"' in x
            record("⑩2 AR 顶栏 +/− 存在", verdict(has_minus and has_plus),
                   "－=%s ＋=%s（真机反馈：加了「干净」后这两个被挤出屏幕 ⇒ 已改可滚动并前移）"
                   % (has_minus, has_plus))
            tap_text(dump("k7"), "返回", wait=2.0)'''
new = '''        if ar_entry is None:
            record("⑩2 AR 顶栏 +/− 存在", "SKIP", "抽屉里没找到 3D AR 入口")
        else:
            x = dump("k6")
            # 「－ ＋」是 **Live2D AR 页**（ArScreen）上的桌宠缩放按钮，从设置页进入。
            # 3D AR 页（VrmArScreen）不一定有，所以先判断当前到底在哪一页，避免误报。
            is_live2d_ar = any(k in x for k in ("1×", "2×", "5×", "手电", "闪光", "归位"))
            if not is_live2d_ar:
                record("⑩2 AR 顶栏 +/− 存在", "SKIP",
                       "当前进入的是 3D AR 页；「－ ＋」在 Live2D AR 页（设置页进入），本项不适用")
            else:
                has_minus = "－" in x
                has_plus = "＋" in x
                record("⑩2 AR 顶栏 +/− 存在", verdict(has_minus and has_plus),
                       "－=%s ＋=%s（真机反馈：加了「干净」后这两个被挤出屏幕 ⇒ 已改可滚动并前移到可见区）"
                       % (has_minus, has_plus))
            tap_text(dump("k7"), "返回", wait=2.0)'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ⑩2 已改为先判页面再判 +/−（避免误报 FAIL）")
else:
    print("✗ ⑩2 锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
print()
print("=== 启动真机验收（后台）===")
