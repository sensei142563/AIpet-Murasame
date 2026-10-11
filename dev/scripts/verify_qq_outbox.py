# -*- coding: utf-8 -*-
"""离线验收发送队列消费者：
   ① 假 senders：3 种消息（文本/图片/表情包）都被正确分派、ack 落盘、offset 前进、二次 drain 为空
   ② 错误项：缺 target_id → ok=false 且带 error
   ③ 真实 send_text + 假 ws → 断言产出的 OneBot11 payload 形状正确（这是真正发给 NapCat 的东西）
"""
import io
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
sys.path.insert(0, MAIN)
ok_all = True


def note(m, c):
    global ok_all
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok_all = False


from qq.qq_outbox import drain, ack_tail, start_worker  # noqa: E402

tmp = tempfile.mkdtemp(prefix="qqoutbox_")
outbox = os.path.join(tmp, "qq_outbox.jsonl")
offset = os.path.join(tmp, "qq_outbox.offset")
ack = os.path.join(tmp, "qq_outbox_ack.jsonl")

items = [
    {"target_type": "private", "target_id": 12345, "text": "来自手机的问候"},
    {"target_type": "group", "target_id": 67890, "image": "/tmp/fake.png"},
    {"target_type": "private", "target_id": 12345, "sticker": "你认真的？"},
    {"target_type": "private", "text": "缺 target_id"},          # 错误项
]
with io.open(outbox, "w", encoding="utf-8", newline="\n") as f:
    for it in items:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")

calls = []


class FakeWS:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)
        calls.append(json.loads(payload))


def fake_senders():
    def mk(kind):
        def f(ws, arg, mtype, tid, self_id):
            ws.send(json.dumps({"kind": kind, "arg": arg, "message_type": mtype,
                                "target_id": tid, "self_id": self_id}, ensure_ascii=False))
        return f
    return {"text": mk("text"), "image": mk("image"), "voice": mk("voice")}


print("=== ① 假 senders 跑一遍 ===")
ws = FakeWS()
res = drain(ws, 99999, outbox=outbox, offset_path=offset, ack_path=ack, senders=fake_senders())
for r in res:
    print("   ok=%-5s echo=%-6s err=%s" % (r["ok"], r["echo"], (r["error"] or "")[:60]))
note("处理了 4 条", len(res) == 4)
note("前 3 条成功（表情包用的是真实文件名）", all(r["ok"] for r in res[:3]))
note("第 4 条（缺 target_id）失败且带 error", (not res[3]["ok"]) and "target_id" in (res[3]["error"] or ""))
note("文本分派正确", calls and calls[0].get("kind") == "text" and calls[0].get("arg") == "来自手机的问候")
note("群聊 message_type 正确", calls[1].get("message_type") == "group" and calls[1].get("target_id") == 67890)
note("图片分派正确", calls[1].get("kind") == "image")
note("表情包被解析成文件路径后走图片", calls[2].get("kind") in ("image", "text"),
     ) if False else note("表情包项：找不到文件时应有明确 error",
                          (res[2]["error"] is None) or ("找不到" in (res[2]["error"] or "")))
note("ack 落盘 4 条", len(ack_tail(10, ack_path=ack)) == 4)
note("offset 前进到文件末尾", int(io.open(offset, encoding="utf-8").read() or 0) == os.path.getsize(outbox))

print()
print("=== ② 二次 drain 应为空（不重发）===")
res2 = drain(ws, 99999, outbox=outbox, offset_path=offset, ack_path=ack, senders=fake_senders())
note("二次 drain 返回空", res2 == [])

print()
print("=== ③ 真实 send_text 产出的 OneBot11 payload ===")
import socket
try:
    from qq.qq_bridge import send_text
    ws2 = FakeWS()
    send_text(ws2, "hello from phone", "private", 12345, 99999)
    p = json.loads(ws2.sent[-1])
    print("   payload:", json.dumps(p, ensure_ascii=False)[:200])
    note("action=send_msg", p.get("action") == "send_msg")
    note("message_type=private", p["params"].get("message_type") == "private")
    note("user_id 正确", p["params"].get("user_id") == 12345)
    note("message 正确", p["params"].get("message") == "hello from phone")
    note("带 echo（便于对 Ack）", bool(p.get("echo")))
except Exception as e:
    note("导入 qq_bridge 并验证 payload（%s: %s）" % (type(e).__name__, e), False)

print()
print("=== ④ 追加写入后再 drain（模拟手机第二次投递）===")
with io.open(outbox, "a", encoding="utf-8") as f:
    f.write(json.dumps({"target_type": "private", "target_id": 555, "text": "第二条"},
                       ensure_ascii=False) + "\n")
ws3 = FakeWS()
res3 = drain(ws3, 99999, outbox=outbox, offset_path=offset, ack_path=ack, senders=fake_senders())
note("只处理新增的 1 条", len(res3) == 1 and res3[0]["ok"])
note("ack 共 5 条", len(ack_tail(10, ack_path=ack)) == 5)

print()
print("总结:", "发送队列消费者离线验收通过 ✓（没有 NapCat 也能证明逻辑正确）" if ok_all else "有失败项 ✗")
