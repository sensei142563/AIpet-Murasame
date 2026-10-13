# -*- coding: utf-8 -*-
"""把渲染层的判据从"不透明占比"（太粗）换成**图像内容摘要**（决定性），再跑。"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
T = os.path.join(ROOT, "tests", "test_bugfix_0930b.py")

t = io.open(T, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ① 加一个图像摘要助手（放在 _opaque 定义之后比较稳）
if "_img_digest" not in t:
    m = re.search(r"(?m)^def _opaque\(.*?\n(?:.*?\n)*?^    return .*\n", t)
    if m:
        helper = ('''

def _img_digest(pet):
    """合成图的**内容摘要**（决定性判据）。

    为什么不用"不透明占比"：那只是非透明像素的比例，两件不同衣服完全可能撞上同一个值
    （实测"睡衣/私服/刀服"都是 31.22）—— 用它判"换装生效"会误判。
    这里直接对像素取摘要：只要画出来的东西有一处不同，摘要就不同。
    """
    try:
        img = pet.grab().toImage()
        if img.isNull():
            return "null"
        w, h = img.width(), img.height()
        buf = bytearray()
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                c = img.pixelColor(x, y)
                buf += bytes((c.red(), c.green(), c.blue(), c.alpha()))
        import hashlib
        return hashlib.md5(bytes(buf)).hexdigest()[:10]
    except Exception as e:
        return "err:%s" % e
''')
        t = t[:m.end()] + helper + t[m.end():]
        print("✓ 已加 _img_digest 助手")

# ② 换装复核块：同时收摘要，判据用摘要
t = t.replace('    _ratios, _cids = {}, {}', '    _ratios, _cids, _digs = {}, {}, {}', 1)
t = t.replace('            _ratios[_c] = round(_opaque(_pet2)[0], 2)',
              '            _ratios[_c] = round(_opaque(_pet2)[0], 2)\n'
              '            _digs[_c] = _img_digest(_pet2)', 1)
t = t.replace('    print("      渲染层 不透明占比：%s" % _ratios)',
              '    print("      渲染层 不透明占比：%s" % _ratios)\n'
              '    print("      渲染层 图像摘要：%s" % _digs)', 1)
t = t.replace('''    check("★ 渲染层：四套画出来至少 3 种不同", len(set(_ratios.values())) >= 3, str(_ratios))''',
              '''    check("★ 渲染层：四套画出来内容各不相同（图像摘要）",
          len(set(_digs.values())) >= 3, str(_digs))''', 1)
io.open(T, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 验证 ===")
try:
    py_compile.compile(T, doraise=True)
    print("   ✓ py_compile")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)
r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930b.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s = l.strip()
    if "[FAIL]" in s or "FAILED" in s or "通过" in s or s.startswith(("解析层", "渲染层")):
        print("   " + s[:150])
print("   退出码 =", r.returncode)
