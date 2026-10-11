# -*- coding: utf-8 -*-
"""回退 accept_all.py 后，用**单行/无缩进风险**的改法重做三处：
  ④ 最多 5 次返回
  ⑤b 触发前清空 live2d.log
  ⑥ 离线识别停用时判 SKIP（只改 record 那一行，不动缩进）"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

print("=== 回退 ===")
r0 = subprocess.run(["git", "-C", MAIN, "checkout", "--", "dev/scripts/accept_all.py"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + (r0.stdout or r0.stderr or "✓ 已回退").strip()[:120])

a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

# ④ 最多 5 次（纯文本替换，安全）
a = a.replace("for _ in range(3):", "for _ in range(5):", 1)
a = a.replace('record("④ 返回键（最多按 3 次必须退出）"', 'record("④ 返回键（最多按 5 次必须退出）"', 1)
print("✓ ④ 改为最多 5 次")

# ⑤b 清日志（插在"点离线音色"那行之前，保持同样的缩进）
m = re.search(r"(?P<ind>[ \t]*)sel = tap_text_any\(dump\(\"b5\"\), \[\"离线音色\"\]\)", a)
if m:
    ind = m.group("ind")
    a = (a[:m.start()]
         + ind + "if not DRY:   # 先清空：否则读到的是之前累积的旧 [tts] 行（上一轮就是这么误判的）\n"
         + ind + "    adb(\"shell\", \"rm\", \"-f\", EXT + \"/live2d.log\")\n"
         + a[m.start():])
    print("✓ ⑤b 已加清日志")
else:
    print("⚠ ⑤b 锚点未命中")

# ⑥ 只改 record 那一行（不动缩进）
old6 = 'record("⑥ Silero VAD", verdict(lines),'
new6 = ('record("⑥ Silero VAD",\n'
        '                       ("SKIP" if "1" not in (adb("shell", "cat", EXT + "/asr_offline_enabled.txt") or "").strip()[:1]\n'
        '                        else verdict(lines)),')
if old6 in a:
    a = a.replace(old6, new6, 1)
    print("✓ ⑥ 已改为：离线识别停用 ⇒ SKIP（只动这一行）")
else:
    print("⚠ ⑥ 锚点未命中")

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
print(out[j:] if j > 0 else out[-700:])
