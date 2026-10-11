# -*- coding: utf-8 -*-
"""① 修 qq_outbox：只消费完整行（以 \\n 结尾）② 修我写反的那条测试断言 ③ 重跑"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
OB = os.path.join(MAIN, "qq", "qq_outbox.py")
A = os.path.join(MAIN, "dev", "scripts", "qq_outbox_adversarial.py")

t = io.open(OB, encoding="utf-8").read().replace("\r\n", "\n")
old = """                line = f.readline()
                if not line:
                    break
                consumed = f.tell()
                line = line.strip()
                if not line:
                    off = consumed
                    continue"""
new = """                line = f.readline()
                if not line:
                    break
                # **只消费完整行**：手机端是并发追加的（api.py 的 /qq/queue/send 用 "a" 模式
                # 写 json+"\\n"），所以 readline() 很可能读到"写到一半、还没有换行"的半行。
                # 原实现在判断完整性之前就记下 consumed 并推进 offset ⇒ 半行被当成已消费，
                # 等后半截到来时会被当作新的垃圾行读掉 ⇒ **这条消息永远不会发出**（静默丢消息）。
                # 对抗测试已复现：半行场景下 offset=87（应 67），补完后该条一条都发不出去。
                if not line.endswith("\\n"):
                    break
                consumed = f.tell()
                line = line.strip()
                if not line:
                    off = consumed          # 空行直接跳过（不产生 ack 噪音）
                    continue"""
if old in t:
    t = t.replace(old, new, 1)
    io.open(OB, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ qq_outbox.drain 已改为只消费完整行")
else:
    print("✗ 锚点未命中")
    sys.exit(1)

# 修我写反的断言
a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
a = a.replace('''note("空行不产生 ack 噪音", sum(1 for x in r if x.get("item") is None) >= 1, "结果项 %d" % len(r))''',
              '''# 4 条垃圾 + 1 条正常 ⇒ 期望 3 个结果项：
#   空行与纯空白被跳过（不产生任何结果/ack）；两条"是 JSON 但不是对象"的会各记一个错误；
#   最后一条正常发出。（我第一版断言写成"至少 1 项没有 item"，把期望写反了 —— 空行本就不该有结果项。）
note("空行/纯空白被跳过（4 垃圾 + 1 正常 ⇒ 恰 3 个结果项）", len(r) == 3, "结果项 %d" % len(r))''', 1)
io.open(A, "w", encoding="utf-8", newline="\n").write(a)
print("✓ 已修正被写反的断言")

print()
print("=== 语法检查 ===")
for f in (OB, A):
    r = subprocess.run([sys.executable, "-c",
                        "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % f],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("   %-26s %s" % (os.path.basename(f), "OK" if r.returncode == 0 else "FAIL " + (r.stderr or "")[:200]))

print()
print("=== 重跑对抗测试 ===")
r = subprocess.run([sys.executable, "-u", A], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=900, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== ②")
print(out[i:] if i > 0 else out)
print("   退出码:", r.returncode)
