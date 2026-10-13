# -*- coding: utf-8 -*-
"""① 把 venv 里 pip 残留（~orch / ~umpy*）移到 dev/tmp/venv_junk（不直接删）
   ② 重启桌宠（PYTHONUNBUFFERED=1，输出落文件），等它起来
   ③ 报出控制台里的关键行（尤其 [UIA] 是否还告警）与窗口/端口状态
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
SP = os.path.join(ROOT, "runtime", "venv", "Lib", "site-packages")
JUNK = os.path.join(ROOT, "dev", "tmp", "venv_junk")
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

print("=== ① 移走 pip 残留 ===")
os.makedirs(JUNK, exist_ok=True)
moved = 0
for name in os.listdir(SP):
    if name.startswith("~"):
        src = os.path.join(SP, name)
        dst = os.path.join(JUNK, name)
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst, ignore_errors=True) if os.path.isdir(dst) else os.remove(dst)
            shutil.move(src, dst)
            print("   已移走: %s" % name)
            moved += 1
        except Exception as e:
            print("   移走 %s 失败: %s" % (name, e))
print("   共 %d 个" % moved)

print()
print("=== ② 校验 venv 干净（pip check + 关键导入）===")
r = subprocess.run([VENV, "-m", "pip", "check"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
print("   pip check:", ((r.stdout or "") + (r.stderr or "")).strip()[:300] or "(无输出)")
r2 = subprocess.run([VENV, "-m", "pip", "list"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600)
warn = [l for l in ((r2.stdout or "") + (r2.stderr or "")).splitlines() if "invalid distribution" in l]
print("   pip list 里的 invalid distribution 告警: %d 条 %s"
      % (len(warn), "✓ 已消除" if not warn else "✗ 仍有"))

print()
print("=== ③ 重启桌宠 ===")
env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
out = os.path.join(ROOT, "dev", "shots", "_pet_out.txt")
err = os.path.join(ROOT, "dev", "shots", "_pet_err.txt")
for f in (out, err):
    if os.path.exists(f):
        os.remove(f)
of = io.open(out, "wb")
ef = io.open(err, "wb")
p = subprocess.Popen([VENV, "run.py"], cwd=ROOT, env=env, stdout=of, stderr=ef,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
print("   已启动 PID=%d，等待 75 秒…" % p.pid)
time.sleep(75)
of.close()
ef.close()
print("   主进程是否还活着:", p.poll() is None)

body = ""
for f in (out, err):
    if os.path.exists(f):
        body += io.open(f, encoding="utf-8", errors="replace").read()
lines = [l.rstrip() for l in body.splitlines() if l.strip()]
print()
print("=== 控制台关键行（共 %d 行）===" % len(lines))
KEY = ("[UIA]", "[插件]", "[AIpet]", "[Live2D]", "错误", "Error", "Traceback", "失败",
       "不可用", "回退", "退回")
shown = 0
for l in lines:
    if any(k in l for k in KEY):
        print("   " + l[:165])
        shown += 1
        if shown > 40:
            break
if not shown:
    print("   （没有关键行；最后 15 行如下）")
    for l in lines[-15:]:
        print("   " + l[:165])
