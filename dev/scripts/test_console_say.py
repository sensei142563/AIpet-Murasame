# -*- coding: utf-8 -*-
"""测新的控制台行为：应看到
   · 收到一次合成请求
   ✅ 模型已彻底起来
   [hh:mm:ss] 说：「…」
   ⚠ 报错行
  而日志里要有**全部**输出。用假子进程模拟 api.py。
"""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
LOG = os.path.join(ROOT, "data", "tts_service.log")
SAY = os.path.join(ROOT, "data", "tts_say.log")
CFG = os.path.join(ROOT, "data", "tts_console.json")
FAKE = os.path.join(ROOT, "dev", "scripts", "_fake_tts.py")

# 假服务：模仿 api.py 的输出顺序，并写一句"要说的话"到桥文件
io.open(FAKE, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
import io, os, sys, time
def out(s):
    sys.stdout.write(s + "\\n"); sys.stdout.flush()
out("INFO:     未指定默认参考音频")
out("INFO:     半精: True")
out("INFO:     编码格式: wav")
time.sleep(0.3)
out('INFO:     127.0.0.1:51234 - "POST /tts HTTP/1.1" 200 OK')
time.sleep(0.3)
p = os.path.join("data", "tts_say.log")
with io.open(p, "a", encoding="utf-8") as f:
    f.write("%.3f\\t今天有点累呢，主人\\n" % time.time())
time.sleep(0.8)
out("INFO:     Application startup complete.")
out("INFO:     Uvicorn running on http://0.0.0.0:9880 (Press CTRL+C to quit)")
time.sleep(0.5)
out('INFO:     127.0.0.1:51235 - "POST /tts HTTP/1.1" 200 OK')
with io.open(p, "a", encoding="utf-8") as f:
    f.write("%.3f\\t那要不要先休息一会儿？\\n" % time.time())
time.sleep(0.5)
out("ERROR:    测试用的报错行")
time.sleep(0.5)
''')

io.open(CFG, "w", encoding="utf-8", newline="\n").write(json.dumps({
    "title": "AIpet 语音服务 · 丛雨（GPT-SoVITS 9880）",
    "log": LOG, "say_log": SAY, "port": "9880",
    "lines": ["AIpet 语音服务 · 丛雨",
              "GPT-SoVITS  ·  服务端口 9880  ·  模型：murasame-gpt.ckpt / murasame-sovits.pth",
              "详细日志写在 data\\tts_service.log（本窗口故意保持安静）",
              "关闭本窗口 = 停止语音服务；不需要语音时可在设置里关掉「短语音」。"],
}, ensure_ascii=False, indent=1))

for p in (LOG, SAY):
    try:
        os.remove(p)
    except Exception:
        pass

print("=== 跑外壳（假服务），看控制台输出 ===")
r = subprocess.run([sys.executable, os.path.join(ROOT, "tool", "tts_console.py"), CFG,
                    "--", FAKE],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=300)
print("   退出码:", r.returncode)
print("   ---- 控制台 ----")
for l in (r.stdout or "").split("\n"):
    if l.strip() or l == "":
        print("   | " + l[:112])
if (r.stderr or "").strip():
    print("   ---- stderr ----")
    for l in (r.stderr or "").split("\n")[:8]:
        print("   ! " + l[:112])

print()
print("=== 日志（应有全部输出，含被控制台吞掉的 INFO 行）===")
if os.path.isfile(LOG):
    ls = [x for x in io.open(LOG, encoding="utf-8", errors="replace").read().split("\n") if x.strip()]
    print("   共 %d 行" % len(ls))
    for x in ls:
        print("   >", x[:112])
else:
    print("   ✗ 没有日志")

print()
print("=== 桥文件内容 ===")
if os.path.isfile(SAY):
    for x in io.open(SAY, encoding="utf-8", errors="replace").read().split("\n"):
        if x.strip():
            print("   ~", x[:100])
else:
    print("   （无）")
