# -*- coding: utf-8 -*-
"""收尾 test_bugfix_0930 最后 2 项：
  ① pcl_launcher/widgets.py 加「状态」页开关（_add_slider + 载入时 _set_slider 回填）
  ② classes/murasame_class.py 的右键菜单「她的状态」受同一开关管
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
if '"status_page_enabled", "「状态」页"' in t:
    print("① · 开关项已存在")
else:
    anchor = '        self._add_slider("qq_vision_enabled", "QQ 图片识别", ["false", "true"], "true")'
    new = (anchor + "\n"
           "        # 「状态」页/状态窗可以在设置里关掉（用户要求：「这个『状态』无法『不启用』\n"
           "        # 这一点不好，也应该做成可以选择是否开启的」）。默认开 ⇒ 不影响老用户。\n"
           "        self._add_slider(\"status_page_enabled\", \"「状态」页\", [\"false\", \"true\"], \"true\")")
    if anchor in t:
        t = t.replace(anchor, new, 1)
        print("① ✓ 已加 _add_slider(\"status_page_enabled\", \"「状态」页\", …)")
    else:
        print("① ✗ 锚点未命中")

if '_set_slider("status_page_enabled"' not in t:
    a2 = '        self._set_slider("qq_vision_enabled", cfg.get("qq_vision_enabled", "true"))'
    n2 = (a2 + "\n"
          '        self._set_slider("status_page_enabled", cfg.get("status_page_enabled", "true"))')
    if a2 in t:
        t = t.replace(a2, n2, 1)
        print("① ✓ 已加载入回填 _set_slider(\"status_page_enabled\", …)")
    else:
        print("① ✗ 载入锚点未命中")
io.open(W, "w", encoding="utf-8", newline="\n").write(t)

# ---------- ② murasame_class.py ----------
M = os.path.join(ROOT, "classes", "murasame_class.py")
m = io.open(M, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
lines = m.split("\n")
k = next((i for i, l in enumerate(lines) if '_act_seen = item(_ai, "她的状态 / 记忆 / 提醒")'), None)
print()
if k is None:
    print("② ✗ 没找到菜单项行")
elif "status_page_enabled" in m:
    print("② · 已有 status_page_enabled")
else:
    # 找到该行的缩进
    ind = re.match(r"(\s*)", lines[k]).group(1)
    guard = [
        ind + "# 「状态」页可以在设置里关掉（config.json 的 status_page_enabled，默认开）——",
        ind + "# 关掉后右键菜单里也不该再有这一项，否则点开是个空窗。",
        ind + "_sp_on = True",
        ind + "try:",
        ind + "    from tool.config import as_bool as _ab_sp, get_config as _gc_sp",
        ind + '    _sp_on = _ab_sp(_gc_sp(os.path.join(_app_base_dir(), "config.json"))',
        ind + '                    .get("status_page_enabled"), True)',
        ind + "except Exception:",
        ind + "    _sp_on = True",
        ind + "if _sp_on:",
    ]
    lines = lines[:k] + guard + lines[k:]
    # 菜单项两行也要缩进一级（item 与 connect）
    j = k + len(guard)
    for x in range(j, min(j + 3, len(lines))):
        if lines[x].startswith(ind) and lines[x].strip():
            lines[x] = "    " + lines[x]
        else:
            break
    io.open(M, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("② ✓ 已加开关判断（菜单项整体缩进一级）")
    for x in range(k, min(k + len(guard) + 3, len(lines))):
        print("      %5d| %s" % (x + 1, lines[x].rstrip()[:118]))

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
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
