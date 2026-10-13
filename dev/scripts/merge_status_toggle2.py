# -*- coding: utf-8 -*-
"""按**真实缩进**重做收尾两项（上次两处都插错了缩进/位置，已 git checkout 还原）：
  ① widgets.py：开关项加在 8 空格处；载入回填加在 12 空格的 try 块内
  ② murasame_class.py：菜单项在 16 空格处，用 if _sp_on: 包住并把 3 行缩进到 20
"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

# ---------- ① widgets.py ----------
W = os.path.join(ROOT, "pcl_launcher", "widgets.py")
t = io.open(W, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
a1 = '        self._add_slider("qq_vision_enabled", "QQ 图片识别", ["false", "true"], "true")'
n1 = (a1 + "\n"
      '        # 「状态」页 / 状态窗可以在设置里关掉（用户要求：「这个『状态』无法『不启用』\n'
      '        # 这一点不好，也应该做成可以选择是否开启的」）。默认开 ⇒ 不影响老用户。\n'
      '        self._add_slider("status_page_enabled", "「状态」页", ["false", "true"], "true")')
if '"status_page_enabled", "「状态」页"' not in t:
    assert a1 in t, "add_slider 锚点未命中"
    t = t.replace(a1, n1, 1)
    print("① ✓ 已加开关项（8 空格）")
a2 = '            self._set_slider("qq_vision_enabled", cfg.get("qq_vision_enabled", "true"))'
n2 = (a2 + "\n"
      '            self._set_slider("status_page_enabled", cfg.get("status_page_enabled", "true"))')
if '_set_slider("status_page_enabled"' not in t:
    assert a2 in t, "set_slider 锚点未命中（注意缩进是 12 空格）"
    t = t.replace(a2, n2, 1)
    print("① ✓ 已加载入回填（12 空格，try 块内）")
io.open(W, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ② murasame_class.py ----------
M = os.path.join(ROOT, "classes", "murasame_class.py")
m = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = m.split("\n")
k = None
for i, l in enumerate(lines):
    if l.strip() == '_act_seen = item(_ai, "她的状态 / 记忆 / 提醒")':
        k = i
        break
print()
if k is None:
    print("② ✗ 没找到菜单项行")
elif "status_page_enabled" in m:
    print("② · 已存在")
else:
    ind = re.match(r"(\s*)", lines[k]).group(1)
    print("② 菜单项在第 %d 行，缩进 %d 空格" % (k + 1, len(ind)))
    guard = [
        ind + "# 「状态」页可以在设置里关掉（config.json 的 status_page_enabled，默认开）——",
        ind + "# 关掉后右键菜单里也不该再有这一项：点开只会是个空窗，不如没有。",
        ind + "_sp_on = True",
        ind + "try:",
        ind + "    from tool.config import as_bool as _ab_sp, get_config as _gc_sp",
        ind + '    _sp_on = _ab_sp(_gc_sp(os.path.join(os.getcwd(), "config.json"))',
        ind + '                    .get("status_page_enabled"), True)',
        ind + "except Exception:",
        ind + "    _sp_on = True",
        ind + "if _sp_on:",
    ]
    # 菜单项那 3 行（item / setToolTip / connect）整体再缩进 4
    j = k
    n_moved = 0
    while j < len(lines) and n_moved < 3:
        if lines[j].startswith(ind) and lines[j].strip():
            lines[j] = "    " + lines[j]
            n_moved += 1
        j += 1
    lines = lines[:k] + guard + lines[k:]
    io.open(M, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("② ✓ 已包住 %d 行菜单项" % n_moved)
    for x in range(k, min(k + len(guard) + n_moved + 1, len(lines))):
        print("      %5d| %s" % (x + 1, lines[x].rstrip()[:120]))

print()
print("=== 验证 ===")
for f in ("pcl_launcher/widgets.py", "classes/murasame_class.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:300]))
        sys.exit(1)
r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "体检" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
