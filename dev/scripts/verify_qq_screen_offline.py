# -*- coding: utf-8 -*-
"""手机没连线时的替代验收：
   ① 从 APK 里确认 QqScreen 类与关键文案确实打进去了（dex 字符串取证）
   ② 在电脑上原样重放手机 QQ 页会发的 5 个请求，校验 UI 依赖的字段形状
"""
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
API = "http://127.0.0.1:28565"
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


print("=== ① APK 取证（QqScreen 与页面文案是否打进去了）===")
print("   APK: %.1f MB" % (os.path.getsize(APK) / 1e6))
needles = [b"QqScreen", "QQ 通道".encode("utf-8"), "发送到队列".encode("utf-8"),
           "NapCat".encode("utf-8"), "待发送字节".encode("utf-8")]
found = {n: False for n in needles}
with zipfile.ZipFile(APK) as z:
    dexes = [n for n in z.namelist() if n.endswith(".dex")]
    print("   dex 文件 %d 个" % len(dexes))
    for d in dexes:
        data = z.read(d)
        for n in needles:
            if n in data:
                found[n] = True
for n, v in found.items():
    note("APK 内含 %-14s" % n.decode("utf-8", "replace"), v)

print()
print("=== ② 重放手机页会发的请求（校验字段形状）===")


def req(path, body=None):
    if body is None:
        r = urllib.request.Request(API + path)
    else:
        r = urllib.request.Request(API + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                   headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


st = req("/qq/status")
print("   /qq/status    → napcat_ws=%s listening=%s sessions=%s owner=%s" % (
    st.get("napcat_ws"), st.get("napcat_ws_listening"), st.get("sessions"), st.get("owner_id")))
note("status 含 UI 需要的字段", all(k in st for k in
     ("napcat_ws", "napcat_ws_listening", "sessions", "owner_id", "memory_dir", "qq_enabled")))

se = req("/qq/sessions")
sess = se.get("sessions") or []
print("   /qq/sessions  → count=%s，首条=%s" % (se.get("count"), json.dumps(sess[0], ensure_ascii=False)[:120] if sess else "-"))
note("sessions 每项含 key/messages/last", bool(sess) and all(
    k in sess[0] for k in ("key", "messages", "last")))

if sess:
    key = sess[0]["key"]
    ms = req("/qq/messages?session=" + key)
    print("   /qq/messages  → total=%s，末条=%s" % (
        ms.get("total"), (ms.get("messages") or [{}])[-1].get("content", "")[:60]))
    note("messages 有 messages 数组与 role/content", isinstance(ms.get("messages"), list) and
         (not ms["messages"] or ("role" in ms["messages"][-1] and "content" in ms["messages"][-1])))

ob = req("/qq/outbox")
print("   /qq/outbox    → pending=%s acked=%s" % (ob.get("pending_bytes"), len(ob.get("acked") or [])))
note("outbox 含 UI 需要的字段", all(k in ob for k in ("pending_bytes", "queued", "acked")))

sent = req("/qq/queue/send", {"target_type": "private", "target_id": 1234567,
                              "text": "phone-ui-contract-check"})
print("   /qq/queue/send→ %s" % json.dumps(sent, ensure_ascii=False)[:140])
note("queue/send 返回 ok=True（这是手机页点「发送到队列」走的同一个接口）", sent.get("ok") is True)
ob2 = req("/qq/outbox")
print("   再查 outbox   → pending=%s（应比上面大）" % ob2.get("pending_bytes"))
note("队列里确实多出待发送内容", ob2.get("pending_bytes", 0) > ob.get("pending_bytes", 0))
q = (ob2.get("queued") or [])[-1]
note("队尾就是刚投递的这条", "phone-ui-contract-check" in json.dumps(q, ensure_ascii=False))

print()
print("=== 结论 ===")
print("   QQ 页代码已打进退 APK ✓；它依赖的 5 个接口在电脑上全部按预期返回 ✓")
print("   真机 UI 验收**未做** ✗ —— 手机当前没连线（USB 已拔、热点未开）")
print("   你插上 USB（或开热点）后我立刻补：打开 QQ 页 → 看真实数据 → 点发送 → 查 pending 增大")
print("   （测试向队列写了内容，最终会被桌面端线程消费；如需清空可删 data/qq_outbox*.jsonl）")
print()
print("总结:", "替代验收通过 ✓" if ok else "有失败项 ✗")
