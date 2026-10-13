# -*- coding: utf-8 -*-
"""① 把「预载语音服务 / 预载视觉服务」从顶部按钮行挪进「快捷工具」卡片，并统一高度
   ② 打印「模型状态」的取值/显示代码（_apply_models 等），定位"不起作用"的原因
"""
import io
import os
import py_compile
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ① 顶部行只留三个启动按钮 ----------
OLD1 = "        for b in (self.btn_pet, self.btn_qq, self.btn_wx, self.btn_preload, self.btn_vpreload):\n            row.addWidget(b)"
NEW1 = ("        # ★ 2026-10-14（主人反馈）：顶部原来挤了 5 个按钮（启动桌宠/QQ/微信 + 两个预载），\n"
        "        #   又挤又不好看。两个「预载」已挪到下面的「快捷工具」卡片里。\n"
        "        for b in (self.btn_pet, self.btn_qq, self.btn_wx):\n"
        "            row.addWidget(b)")
if OLD1 in t:
    t = t.replace(OLD1, NEW1, 1)
    print("✓ ① 顶部行已只留三个启动按钮")
else:
    print("✗ ① 锚点未命中（顶部行）")

# ---------- ② 两个预载按钮去掉 46 高度（和工具按钮一致）----------
n = 0
for nm in ("btn_preload", "btn_vpreload"):
    old = "        self.%s.setMinimumHeight(46)\n" % nm
    if old in t:
        t = t.replace(old, "", 1)
        n += 1
print("✓ ② 去掉 %d 处 setMinimumHeight(46)（与工具按钮统一）" % n)

# ---------- ③ 挪进「快捷工具」----------
OLD3 = """            tr.addWidget(b)
        tr.addStretch()
        tl.addLayout(tr)"""
NEW3 = """            tr.addWidget(b)
        # ★ 2026-10-14：两个「预载」按钮挪到这里 —— 它们本就是"提前把服务热起来"的工具，
        #   放在「快捷工具」里比挤在顶部合理。（主人："首页的两个预加载模型的模块删了，
        #   丑丑的，或者换个地方，放在下面几个板块。"）
        for _pb in (self.btn_preload, self.btn_vpreload):
            tr.addWidget(_pb)
        tr.addStretch()
        tl.addLayout(tr)"""
if OLD3 in t:
    t = t.replace(OLD3, NEW3, 1)
    print("✓ ③ 两个预载按钮已挪进「快捷工具」")
else:
    print("✗ ③ 锚点未命中（快捷工具）")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
try:
    py_compile.compile(P, doraise=True)
    print("✓ py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

print()
print("=== 复核：顶部行与快捷工具 ===")
ls = io.open(P, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(ls, 1):
    if re.search(r"for b in \(self\.btn_|for _pb in|tr\.addStretch|setMinimumHeight\(46\)", l):
        print("   %5d| %s" % (i, l.strip()[:110]))

print()
print("=== ④ 「模型状态」相关代码（定位不起作用的原因）===")
for i, l in enumerate(ls, 1):
    if re.search(r"_apply_models|_probe_models|model_rows|余额|无余额|控制台查看|balance|bal_lbl|_models_probe", l):
        print("   %5d| %s" % (i, l.rstrip()[:118]))
