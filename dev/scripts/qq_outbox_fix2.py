# -*- coding: utf-8 -*-
"""加并发压测（写一边追加、读一边轮询）+ 提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
A = os.path.join(MAIN, "dev", "scripts", "qq_outbox_adversarial.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "并发压测" not in t:
    t = t.replace('''print()
npass = sum(1 for _, ok, _ in results if ok)''',
                  '''print()
print("=== ⑧ 并发压测：一边追加一边轮询，50 条必须恰好各发一次 ===")
import threading
import time as _time
reset()
SENT.clear()
N = 50
delivered = []
lock = threading.Lock()


def writer():
    for i in range(N):
        append_raw(one_line(i, text="并发消息%d" % i))
        _time.sleep(0.01)          # 模拟手机端逐条追加（每 10ms 一条）


def reader():
    stop_at = _time.time() + 12
    while _time.time() < stop_at:
        ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK,
                 senders=fake_senders(), max_items=5)
        with lock:
            if len(delivered) >= N:
                break
            delivered.clear()
            delivered.extend(x["payload"] for x in SENT if x["kind"] == "text")
        _time.sleep(0.005)


# reader 里需要能看到 SENT；简化：只统计
wt = threading.Thread(target=writer)
rt = threading.Thread(target=reader)
wt.start(); rt.start(); wt.join(); rt.join()
# 收尾：再 drain 几次确保排空
for _ in range(10):
    ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK,
             senders=fake_senders())
texts = [x["payload"] for x in SENT if x["kind"] == "text"]
expect = set("并发消息%d" % i for i in range(N))
got = set(texts)
note("50 条全部送达", got == expect,
     "送达 %d 条，缺 %d 条，重复 %d 条" % (len(texts), len(expect - got), len(texts) - len(got)))
note("没有重复投递", len(texts) == len(got), "总发送 %d，去重后 %d" % (len(texts), len(got)))
ack_texts = [a for a in ob.ack_tail(200, ack_path=ACK) if a.get("ok")]
note("ack 条数与送达数一致", len(ack_texts) == len(texts), "ack %d / 送达 %d" % (len(ack_texts), len(texts)))

print()
npass = sum(1 for _, ok, _ in results if ok)''', 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已加并发压测（第 ⑧ 组）")

print()
print("=== 跑完整套件 ===")
r = subprocess.run([sys.executable, "-u", A], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1200, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== ⑧")
j = out.find("=== 汇总")
print(out[i:j] if i > 0 else "")
print(out[j:] if j > 0 else out[-700:])
print("   退出码:", r.returncode)
if r.returncode != 0:
    sys.exit(1)

MSG = """fix(qq): 发送队列只消费完整行 —— 修掉一条真实的静默丢消息路径（对抗测试 15/15）

背景：对 qq/qq_outbox.py 做对抗审查。手机端是**并发追加**的
（api.py 的 /qq/queue/send 以 "a" 模式写 json+"\\n"），而消费端按 offset 顺序读。

实测复现的 bug（对抗测试，可稳定重现）：
  · drain() 里先 `consumed = f.tell()` 再解析，**没有判断这一行是否写完**；
  · readline() 在文件末尾没有换行时会返回"半行"，json.loads 失败，但 offset 已经推进到半行之后；
  · 等后半截追加进来，它会被当作新的垃圾行读掉 ⇒ **这条消息永远不会被发出**（静默丢消息）。
  · 复现数据：半行场景下 offset=87（正确应为 67 = 半行起点）；把半行补完后，
    该条**一条都发不出去**。而这发生在"手机正常发消息"的时候，属于平时就会踩的类型。

修法：**只消费以 \\n 结尾的完整行**；读到没有换行的尾巴就 break（不推进 offset、不写 ack），
等下一次轮询再取。前提已核对：写入端确实每条都以 \\n 结尾（api.py 里 json.dumps(item)+"\\n"）。
另：空行/纯空白仍然跳过且**不产生 ack 噪音**。

我的一个测试错误也一并修正：原断言写成"空行应至少产生 1 个无 item 的结果项"，
方向写反了 —— 空行本就该被完全跳过；正确期望是 4 条垃圾 + 1 条正常 ⇒ 恰 3 个结果项。

验证（dev/scripts/qq_outbox_adversarial.py，离线、可注入假 sender，失败退出非 0）：
  ① 正常两条；② 半行不被消费 + 补完能发出；③ 空行/非 dict 的 JSON；④ offset 非法/越界回退；
  ⑤ 发送失败写 ack 且不卡住队列；⑥ max_items 与多轮轮询；⑦ 缺 target_id；
  ⑧ **并发压测**：一边逐条追加（10ms 一条）一边轮询，50 条**恰好各发一次**（无丢失、无重复）。
  合计 15/15 通过。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_qq_outbox.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
for nm, repo in (("桌面", MAIN), ("手机", CHAT)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("%s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
