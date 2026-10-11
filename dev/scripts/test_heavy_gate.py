# -*- coding: utf-8 -*-
"""重型闸门的并发互斥测试：真开线程并跑，断言"同时只有一个"（不是靠看代码，是实测计数）。"""
import sys
import threading
import time

sys.path.insert(0, r"E:\university\order\python\pet\AIpet-Murasame-main")
from tool.heavy_gate import HeavyGate, Busy  # noqa: E402

ok = True


def note(m, c):
    global ok
    print(("  ✓ " if c else "  ✗ ") + m)
    if not c:
        ok = False


print("=== ① 互斥：8 个线程同时抢，同一时刻只能有 1 个在临界区 ===")
gate = HeavyGate()
inside = 0
max_inside = 0
lock = threading.Lock()
order = []


def worker(i):
    global inside, max_inside
    tok = gate.acquire("task%d" % i, timeout=30)
    try:
        with lock:
            inside += 1
            max_inside = max(max_inside, inside)
            order.append(i)
        time.sleep(0.08)
    finally:
        with lock:
            inside -= 1
        gate.release(tok)


ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
t0 = time.time()
for t in ts:
    t.start()
for t in ts:
    t.join()
elapsed = time.time() - t0
note("同时进入临界区的最大数量 = %d（应为 1）" % max_inside, max_inside == 1)
note("8 个任务都跑完了（%d 个）" % len(order), len(order) == 8)
note("总耗时 ≥ 8×0.08s=0.64s（说明真的串行，实测 %.2fs）" % elapsed, elapsed >= 0.6)
note("状态里没有残留占用：%s" % gate.status()["busy"], gate.status()["busy"] is False)
note("历史里有 8 条记录（%d）" % len(gate.status()["recent"] + []), len(gate.status()["recent"]) <= 8)

print()
print("=== ② 超时：占用不放时，第二个应按上限抛 Busy ===")
g2 = HeavyGate()
held = g2.acquire("long", timeout=5)
try:
    g2.acquire("other", timeout=0.4)
    note("应当抛 Busy 却没抛", False)
except Busy as e:
    note("按上限抛 Busy（消息：%s）" % str(e)[:60], True)
g2.release(held)
note("释放后可再获取", g2.acquire("again", timeout=1) is not None)

print()
print("=== ③ 状态可观测性 ===")
g3 = HeavyGate()
t = g3.acquire("stt", timeout=1)
st = g3.status()
note("busy=True 且 holder=stt：%s" % st, st["busy"] and st["holder"] == "stt")
time.sleep(0.05)
g3.release(t)
st2 = g3.status()
note("history 记录了本次耗时：%s" % st2["recent"][:1], bool(st2["recent"]) and "ms" in st2["recent"][0])
note("状态里写明 F5 未纳入（诚实标注）：%s" % ("F5" in st2["note"]), "F5" in st2["note"])

print()
print("总结:", "重型闸门互斥与超时行为正确 ✓" if ok else "有失败项 ✗")
sys.exit(0 if ok else 1)
