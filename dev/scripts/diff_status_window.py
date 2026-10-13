# -*- coding: utf-8 -*-
"""状态窗：旧版（备份）vs 新版（本树/origin_main）的功能级对比。
输出：类/方法清单、用户可见文案、样式机制、数据来源 —— 为"保留我们的 + 融合他的"提供依据。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"
PATH = "classes/status_window.py"


def show(ref):
    if ref is None:
        return io.open(os.path.join(ROOT, PATH), encoding="utf-8", errors="replace").read()
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, PATH)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


NEW = show(None)
OLD = show(REF_BAK)


def report(name, t):
    print("=" * 78)
    print("=== %s（%d 行）===" % (name, len(t.split("\n"))))
    print("--- 类 / 方法 ---")
    for m in re.finditer(r"(?m)^(\s*)class\s+(\w+)(?:\(([^)]*)\))?", t):
        print("   class %-28s %s" % (m.group(2), m.group(3) or ""))
    for m in re.finditer(r"(?m)^(\s*)def\s+(\w+)\s*\(", t):
        print("   %sdef %s" % ("   " if len(m.group(1)) >= 8 else "", m.group(2)))
    print("--- 用户可见文案（中文串，去重、前 40 条）---")
    seen, out = set(), []
    for m in re.finditer(r'"([^"\n]{2,40})"', t):
        s = m.group(1)
        if re.search(r"[\u4e00-\u9fff]", s) and s not in seen:
            seen.add(s)
            out.append(s)
    for s in out[:40]:
        print("   · %s" % s)
    print("--- 样式 / 机制关键点 ---")
    for k in ("WA_StyledBackground", "QDialog#statusWindow", "setStyleSheet", "setAttribute",
              "QScrollArea", "QVBoxLayout", "setWindowFlags", "Qt.Tool", "setWindowOpacity",
              "QGraphicsDropShadowEffect", "resize(", "showFullScreen", "status_page_enabled"):
        if k in t:
            print("   ✓ %s" % k)
    print("--- 数据来源（import / 调用）---")
    for m in sorted(set(re.findall(r"from\s+([\w\.]+)\s+import\s+([\w, ]+)", t))):
        print("   from %s import %s" % m)
    print()


report("旧版（覆盖前备份）", OLD)
report("新版（本树 / origin_main）", NEW)
