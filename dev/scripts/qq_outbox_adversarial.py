# -*- coding: utf-8 -*-
"""QQ 发送队列的对抗测试：重点验证"手机正在追加 ⇒ 读到半行"时会不会丢消息。"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
sys.path.insert(0, MAIN)
from qq import qq_outbox as ob  # noqa: E402

TMP = tempfile.mkdtemp(prefix="qq_out_adv_")
OUTBOX = os.path.join(TMP, "qq_outbox.jsonl")
OFFSET = os.path.join(TMP, "qq_outbox.offset")
ACK = os.path.join(TMP, "qq_outbox_ack.jsonl")

results = []


def note(name, ok, detail=""):
    results.append((name, ok, detail))
    print("   [%s] %-46s %s" % ("PASS" if ok else "FAIL", name, detail[:130]))


SENT = []


def fake_senders():
    def mk(kind):
        def f(ws, payload, ttype, tid, self_id):
            SENT.append({"kind": kind, "payload": payload, "target_type": ttype,
                         "target_id": tid, "self_id": self_id})
        return f
    return {"text": mk("text"), "image": mk("image"), "voice": mk("voice")}


def reset():
    SENT.clear()
    for p in (OUTBOX, OFFSET, ACK):
        if os.path.exists(p):
            os.remove(p)


def append_raw(s, with_newline=True):
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(s + ("\n" if with_newline else ""))


def one_line(i, text=None):
    return json.dumps({"target_type": "private", "target_id": 10001 + i,
                       "text": text or ("消息%d" % i)}, ensure_ascii=False)


print("=== ① 正常两条 ===")
reset()
append_raw(one_line(1))
append_raw(one_line(2))
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("两条都发出", len(SENT) == 2 and all(x["kind"] == "text" for x in SENT), "发送 %d 条" % len(SENT))
note("offset 推进到文件末", ob._read_offset(OFFSET) == os.path.getsize(OUTBOX),
     "offset=%d size=%d" % (ob._read_offset(OFFSET), os.path.getsize(OUTBOX)))

print()
print("=== ②【关键】半行（手机正在追加）不应该被消费掉 ===")
reset()
append_raw(one_line(1))
complete_len = os.path.getsize(OUTBOX)
partial = one_line(2)[:20]          # 只写了前半截，没有换行
append_raw(partial, with_newline=False)
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
off_after = ob._read_offset(OFFSET)
note("只发出了完整的那条", len(SENT) == 1, "发送 %d 条：%s" % (len(SENT), [x["payload"] for x in SENT]))
note("offset 停在半行之前（未吞掉半行）", off_after == complete_len,
     "offset=%d 应为 %d（半行起点）" % (off_after, complete_len))
# 现在把半行补完
with open(OUTBOX, "a", encoding="utf-8") as f:
    f.write(one_line(2)[20:] + "\n")
SENT.clear()
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("补完后第二条能正常发出（不丢消息）", len(SENT) == 1 and "消息2" in str(SENT[0]["payload"]),
     "发送 %d 条：%s" % (len(SENT), [x["payload"] for x in SENT]))

print()
print("=== ③ 空行 / 只有空白 / 非 dict 的 JSON ===")
reset()
append_raw("")
append_raw("   ")
append_raw('"我是一个字符串"')
append_raw("[1,2,3]")
append_raw(one_line(9))
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("不崩，且末尾正常消息仍发出", len(SENT) == 1 and "消息9" in str(SENT[0]["payload"]),
     "发送 %d 条，结果 %d 项" % (len(SENT), len(r)))
# 4 条垃圾 + 1 条正常 ⇒ 期望 3 个结果项：
#   空行与纯空白被跳过（不产生任何结果/ack）；两条"是 JSON 但不是对象"的会各记一个错误；
#   最后一条正常发出。（我第一版断言写成"至少 1 项没有 item"，把期望写反了 —— 空行本就不该有结果项。）
note("空行/纯空白被跳过（4 垃圾 + 1 正常 ⇒ 恰 3 个结果项）", len(r) == 3, "结果项 %d" % len(r))

print()
print("=== ④ 损坏/缺失的 offset 文件 ===")
reset()
append_raw(one_line(1))
open(OFFSET, "w", encoding="utf-8").write("这不是数字")
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("offset 非法时回退到 0 并正常发送", len(SENT) == 1, "发送 %d 条" % len(SENT))
reset()
append_raw(one_line(1))
open(OFFSET, "w", encoding="utf-8").write("999999")
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("offset 大于文件长度时回退（不崩）", len(SENT) == 1, "发送 %d 条" % len(SENT))

print()
print("=== ⑤ 发送失败时的行为（sender 抛异常）===")
reset()
append_raw(one_line(1))
append_raw(one_line(2))


def bad_senders():
    def boom(*a, **k):
        raise RuntimeError("假装 WS 断了")
    return {"text": boom, "image": boom, "voice": boom}


r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=bad_senders())
acks = ob.ack_tail(10, ack_path=ACK)
note("失败会写 ack 且不崩", len(acks) == 2 and all(not a.get("ok") for a in acks),
     "ack %d 条，ok=%s" % (len(acks), [a.get("ok") for a in acks]))
note("失败项被记为已消费（offset 推进）⇒ 至少一次语义下不会卡住",
     ob._read_offset(OFFSET) == os.path.getsize(OUTBOX),
     "offset=%d size=%d" % (ob._read_offset(OFFSET), os.path.getsize(OUTBOX)))

print()
print("=== ⑥ max_items 限制与多次轮询 ===")
reset()
for i in range(25):
    append_raw(one_line(i))
r1 = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK,
              senders=fake_senders(), max_items=20)
n1 = len(SENT)
r2 = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("首批只发 20 条", n1 == 20, "首批 %d" % n1)
note("第二批把剩下 5 条发完", n1 + len(SENT) - n1 == 25 and len(SENT) == 25, "累计 %d" % len(SENT))

print()
print("=== ⑦ 缺少 target_id 的记录 ===")
reset()
append_raw(json.dumps({"text": "没有目标"}, ensure_ascii=False))
append_raw(one_line(3))
r = ob.drain(object(), "999", outbox=OUTBOX, offset_path=OFFSET, ack_path=ACK, senders=fake_senders())
note("缺 target_id 不崩，后续仍发出", len(SENT) == 1, "发送 %d 条" % len(SENT))
note("错误被记进 ack", any("target_id" in str(a.get("error")) for a in ob.ack_tail(5, ack_path=ACK)),
     str([a.get("error") for a in ob.ack_tail(5, ack_path=ACK)])[:110])

print()
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
npass = sum(1 for _, ok, _ in results if ok)
print("=== 汇总：%d/%d 通过 ===" % (npass, len(results)))
for n, ok, d in results:
    if not ok:
        print("   ✗ %s — %s" % (n, d[:150]))
shutil.rmtree(TMP, ignore_errors=True)
print("（临时目录已清理）")
sys.exit(0 if npass == len(results) else 1)
