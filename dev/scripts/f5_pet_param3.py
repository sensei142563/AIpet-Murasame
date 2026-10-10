# -*- coding: utf-8 -*-
"""给 F5 加 pet 参数（正规流程：临时副本 → 语法验证 → 覆盖 → 重启 → 对比两角色音频）。"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\AIpet-Murasame-main"
AUD = r"E:\university\order\python\pet\_audit_fish9269"
F5 = os.path.join(REPO, "longtext", "f5tts_server.py")
TMPF = os.path.join(AUD, "_f5_patched.py")
LOG = os.path.join(AUD, "_f5serve.log")
PY = shutil.which("python") or sys.executable
BASE = "http://127.0.0.1:9881"

src = io.open(F5, encoding="utf-8", newline="").read()
print("=== 当前 InferRequest 与 infer() 区域 ===")
for i, l in enumerate(src.splitlines(), 1):
    if 296 <= i <= 322:
        print("   %5d| %s" % (i, l.rstrip()[:118]))

# ① 在 InferRequest 的 ref_text 之后加 pet
L = src.splitlines(keepends=True)
ci = next((k for k, l in enumerate(L) if "class InferRequest" in l), None)
assert ci is not None, "✗ 无 InferRequest"
ri = next(k for k in range(ci, ci + 12) if re.match(r"\s*ref_text\b", L[k]))
eol = "\r\n" if L[ri].endswith("\r\n") else "\n"
ind = re.match(r"(\s*)", L[ri]).group(1)
if not any("pet" in L[k] for k in range(ci, ci + 14)):
    L.insert(ri + 1, ind + "pet: str = None" + eol)
    print("✓ 加 pet 字段（第 %d 行后）" % (ri + 1))

# ② 在 infer() 体开头插 pet 解析（只改写 req，不动其它逻辑）
fi = next(k for k, l in enumerate(L) if re.match(r"\s*async def infer\(", l))
# 找到函数体第一条语句（缩进比 def 深的第一行）
body = fi + 1
while body < len(L) and not L[body].strip():
    body += 1
bind = re.match(r"(\s*)", L[body]).group(1)
patch = [
    bind + "# pet：由电脑侧按角色 pet.json 的 long_ref_audio/long_ref_text 解析（手机不猜电脑路径）" + eol,
    bind + "_pet = getattr(req, \"pet\", None)" + eol,
    bind + "if _pet:" + eol,
    bind + "    try:" + eol,
    bind + "        _pa, _pt = get_long_ref(_pet)" + eol,
    bind + "        req.ref_audio = req.ref_audio or str(_pa)" + eol,
    bind + "        req.ref_text = req.ref_text or _pt" + eol,
    bind + "    except Exception as _e:" + eol,
    bind + "        print(\"[F5TTS] pet 解析失败 \" + str(_pet) + \": \" + str(_e))" + eol,
]
L = L[:body] + patch + L[body:]
io.open(TMPF, "w", encoding="utf-8", newline="").write("".join(L))
print("✓ 补丁已写入临时副本:", TMPF)

# ③ 独立语法验证（完整报错，不截断）
r = subprocess.run([PY, "-c",
                    "import ast,sys;src=open(r'%s',encoding='utf-8').read();ast.parse(src);print('AST OK')" % TMPF],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("=== 语法验证 ===")
print((r.stdout or "") + (r.stderr or ""))
if r.returncode != 0:
    print("   ✗ 未通过 → **保留原文件不变**（临时副本留作排查）")
    sys.exit(1)
print("   ✓ 通过")

# ④ 覆盖 + 重启
shutil.copyfile(TMPF, F5)
print("=== 已覆盖原文件，重启服务 ===")
subprocess.run(["taskkill", "/F", "/PID", "4464"], capture_output=True)
time.sleep(2)
env = dict(os.environ, PYTHONIOENCODING="utf-8")
with io.open(LOG, "w", encoding="utf-8") as f:
    proc = subprocess.Popen([PY, "-u", "-m", "longtext.f5tts_server"], cwd=REPO, stdout=f,
                            stderr=subprocess.STDOUT, env=env)
print("   pid =", proc.pid)
ok = False
for k in range(28):
    time.sleep(5)
    try:
        rr = subprocess.run(["curl.exe", "-s", "--max-time", "5", BASE + "/health"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12)
        if '"ready":true' in (rr.stdout or "").replace(" ", ""):
            ok = True
            print("   ★ ready ✓")
            break
    except Exception:
        pass
if not ok:
    print("   ✗ 未 ready → 回滚文件并重启")
    subprocess.run(["git", "-C", REPO, "checkout", "--", "longtext/f5tts_server.py"], capture_output=True)
    for pid in (str(proc.pid),):
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    sys.exit(1)

print()
print("=== 验证：同句两角色 ===")
text = "主人，今天也辛苦啦，要不要喝杯热奶茶？"
for pet in ("murasame", "noir"):
    bp = os.path.join(AUD, "_f5pet.json")
    io.open(bp, "w", encoding="utf-8").write(json.dumps({"text": text, "pet": pet}, ensure_ascii=False))
    out = os.path.join(AUD, "pet_%s.wav" % pet)
    t0 = time.time()
    subprocess.run(["curl.exe", "-s", "--max-time", "300", "-X", "POST",
                    "-H", "Content-Type: application/json; charset=utf-8",
                    "--data-binary", "@" + bp, "-o", out, BASE + "/infer"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=360)
    if os.path.isfile(out) and os.path.getsize(out) > 2000:
        with wave.open(out, "rb") as w:
            sec = w.getnframes() / float(w.getframerate())
        print("   %-10s %.2f 秒 · %.1f KB · sha=%s · %.1fs" % (
            pet, sec, os.path.getsize(out) / 1024,
            hashlib.sha256(open(out, "rb").read()).hexdigest()[:16], time.time() - t0))
a, b = os.path.join(AUD, "pet_murasame.wav"), os.path.join(AUD, "pet_noir.wav")
if os.path.isfile(a) and os.path.isfile(b):
    same = hashlib.sha256(open(a, "rb").read()).hexdigest() == hashlib.sha256(open(b, "rb").read()).hexdigest()
    print("   ★ 两角色音频:", "相同 ✗" if same else "**不同 ✓ 各自音色生效 ✓**")
print()
print("=== 服务日志尾部（看用了哪个参考音频）===")
for l in io.open(LOG, encoding="utf-8", errors="replace").read().splitlines()[-6:]:
    print("   " + l.rstrip()[:124])
