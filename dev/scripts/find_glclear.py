# -*- coding: utf-8 -*-
"""定位 native 渲染里的清屏/透明相关代码（glClearColor / glClear / EGL alpha）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\chatter\app\src\main\cpp"
PATS = re.compile(r"(glClearColor|glClear\(|GL_COLOR_BUFFER_BIT|eglChooseConfig|EGL_ALPHA_SIZE|"
                  r"setClearColor|clearColor|GL_BLEND|glBlendFunc|transparent|alpha)", re.I)

if not os.path.isdir(ROOT):
    print("✗ 没有 cpp 目录:", ROOT)
    for d in (r"E:\university\order\python\pet\chatter\app\src\main"):
        print("   ", d, os.listdir(d) if os.path.isdir(d) else "(不存在)")
    sys.exit(0)

hits = 0
for dp, ds, fs in os.walk(ROOT):
    for f in sorted(fs):
        if not f.endswith((".cpp", ".cc", ".c", ".h", ".hpp")):
            continue
        p = os.path.join(dp, f)
        try:
            L = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        except Exception:
            continue
        found = [(i, l) for i, l in enumerate(L, 1) if PATS.search(l)]
        if found:
            rel = os.path.relpath(p, ROOT)
            print("--- %s ---" % rel)
            for i, l in found[:20]:
                print("   %5d| %s" % (i, l.strip()[:120]))
            hits += len(found)

print()
print("=== cpp 目录结构 ===")
for dp, ds, fs in os.walk(ROOT):
    rel = os.path.relpath(dp, ROOT)
    cpp = [f for f in fs if f.endswith((".cpp", ".cc", ".h", ".hpp"))]
    if cpp:
        print("   %s/  %s" % (rel if rel != "." else "", cpp[:8]))
print()
print("总命中行数:", hits)
