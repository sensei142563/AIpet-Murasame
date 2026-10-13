# -*- coding: utf-8 -*-
"""按拍板从 config.example.json 移除上游专用的 4 个键（保留我们在用的 vision_local_model_dir/port）。
先打印再删，删完复跑测试。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
P = os.path.join(ROOT, "config.example.json")

ex = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
print("=== 删除前：全部 vision* 键 ===")
for k in list(ex.keys()):
    if "vision" in k:
        print("   %-28s = %r" % (k, ex[k]))

DROP = ("vision_source", "vision_local_url", "vision_local_command", "vision_local_model")
removed = []
for k in DROP:
    if k in ex:
        removed.append((k, ex.pop(k)))
io.open(P, "w", encoding="utf-8", newline="\n").write(
    json.dumps(ex, ensure_ascii=False, indent=2) + "\n")
print()
print("=== 已移除 %d 个上游专用键 ===" % len(removed))
for k, v in removed:
    print("   - %-24s (原值 %r)" % (k, v))

ex2 = json.loads(io.open(P, encoding="utf-8", errors="replace").read())
print("=== 删除后：仍保留的 vision* 键（我们在用的）===")
for k in list(ex2.keys()):
    if "vision" in k:
        print("   %-28s = %r" % (k, ex2[k]))
print("   JSON 合法 ✓，顶层键 %d 个" % len(ex2))

print()
print("=== 复跑 test_vision_interface ===")
r = subprocess.run([VENV, os.path.join("tests", "test_vision_interface.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
