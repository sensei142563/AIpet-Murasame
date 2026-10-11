# -*- coding: utf-8 -*-
"""容错地修 ⑤b（触发前清日志）与 ⑥（离线识别停用时 SKIP，与 ⑧3 对齐）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

# ⑤b：在"点离线音色"之前插入清日志（容忍缩进）
m = re.search(r"(?P<ind>[ \t]*)sel = tap_text_any\(dump\(\"b5\"\), \[\"离线音色\"\]\)", a)
if m and "rm\", \"-f\", EXT + \"/live2d.log\"" not in a:
    ind = m.group("ind")
    add = (ind + "# 先清空 live2d.log：否则读到的是之前累积的旧 [tts] 行（上一轮就是这么误判的）\n"
           + ind + "if not DRY:\n"
           + ind + "    adb(\"shell\", \"rm\", \"-f\", EXT + \"/live2d.log\")\n")
    a = a[:m.start()] + add + a[m.start():]
    print("✓ ⑤b 已加：触发前清空 live2d.log")
else:
    print("⚠ ⑤b 未插入（可能已有或锚点变了）")

# ⑥：离线识别停用时 SKIP
m6 = re.search(r"(?P<ind>[ \t]*)if tap_text_any\(dump\(\"b6\"\), \[\"识别自检\"\]\):\n"
               r"(?P<ind2>[ \t]*)time\.sleep\(15\)\n"
               r"(?P<ind3>[ \t]*)lg = read_log\(\"vad\.log\"\)\n"
               r"(?P<ind4>[ \t]*)lines = \[l for l in \(lg or \"\"\)\.splitlines\(\) if \"Silero\" in l\]\n"
               r"(?P<ind5>[ \t]*)record\(\"⑥ Silero VAD\", verdict\(lines\),", a)
if m6 and "离线识别当前已停用" not in a:
    ind = m6.group("ind")
    add = (ind + "# 与 ⑧3 对齐：离线识别（SenseVoice）默认停用（其原生库在本机初始化即崩），\n"
           + ind + "# 而 Silero 只在那条路径里初始化 ⇒ 停用时这一项前提不成立，应判 SKIP 而不是 FAIL。\n"
           + ind + "if \"1\" not in (adb(\"shell\", \"cat\", EXT + \"/asr_offline_enabled.txt\") or \"\").strip()[:1]:\n"
           + ind + "    record(\"⑥ Silero VAD\", \"SKIP\",\n"
           + ind + "           \"离线识别当前已停用（其原生库在本机初始化即崩）⇒ Silero 不会被初始化，前提不成立\")\n"
           + ind + "else:\n"
           + m6.group(0).replace(m6.group("ind"), ind + "    ", 1))
    a = a[:m6.start()] + add + a[m6.end():]
    print("✓ ⑥ 已加：离线识别停用 ⇒ SKIP")
else:
    print("⚠ ⑥ 未插入（可能已有或锚点变了）")

io.open(A, "w", encoding="utf-8", newline="\n").write(a)
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
if r.returncode != 0:
    sys.exit(1)
print()
print("=== dry-run ===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
j = out.find("=== 汇总")
print(out[j:] if j > 0 else out[-600:])
