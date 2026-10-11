# -*- coding: utf-8 -*-
"""精确修「启动检查」那一处（读实际文本再改），然后真机重跑验收。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
i = t.find('record("App 启动')
print("=== 现状（前后各 6 行）===")
lo = max(0, t[:i].count("\n") - 6)
print("\n".join("   %4d| %s" % (lo + k + 1, l.rstrip()[:140])
                for k, l in enumerate(t[t[:i].rfind("\n", 0, t.rfind("\n", 0, i)) if False else 0:].split("\n")[:0])) if False else None)
start = t.rfind("\n", 0, i)
start = t.rfind("\n", 0, start)
end = t.find("\n", i)
seg = t[start + 1:end + 1]
for k, l in enumerate(seg.split("\n")):
    print("      " + l.rstrip()[:150])

# 用正则替换整段：从 open_app() 调用到 record("App 启动"...) 那两行
pat = re.compile(r"(?P<ind>[ \t]*)open_app\(\)\n[ \t]*x = dump\(\"a1\"\)\n[ \t]*record\(\"App 启动\"[^\n]*\n(?:[^\n]*\n)?", re.M)
m = pat.search(t)
if m:
    ind = m.group("ind")
    new = (ind + "ok_start = open_app()\n"
           + ind + "x = dump(\"a1\")\n"
           + ind + "# 判据必须是「前台是不是本应用」：原来用 dump 里有没有某段文字，\n"
           + ind + "# 结果被应用市场搜索框里的 chatter 假通过了一次（诊断包 a1.xml 就是市场安装页）。\n"
           + ind + "record(\"App 启动（前台确认）\", verdict(True if DRY else ok_start),\n"
           + ind + "       \"前台=%s · dump %d 字节\" % (resumed_activity() or \"?\", len(x)))\n")
    t = t[:m.start()] + new + t[m.end():]
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("\n✓ 启动检查已改为前台 Activity 判据")
else:
    print("\n⚠ 仍未命中；请手工看上面片段")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 关键行复核 ===")
src = io.open(A, encoding="utf-8").read()
for k in ("def resumed_activity", "def foreground_is_app", "App 启动（前台确认）",
          "ensure_foreground(\"① 3D 页\")", "第一次前台=", "资产种子（UI 判据）"):
    print("   %-34s %s" % (k, "✓" if k in src else "✗"))
