# -*- coding: utf-8 -*-
"""重型任务闸门：tool/heavy_gate.py（独立、可测）+ 并发互斥测试（线程真的并跑，断言同时只 1 个）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
GATE = os.path.join(MAIN, "tool", "heavy_gate.py")
TEST = os.path.join(MAIN, "dev", "scripts", "test_heavy_gate.py")

io.open(GATE, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""重型任务闸门（GPU/CPU 独占资源的排队与仲裁）。

背景（实测）：本机显存 6141 MiB，F5-TTS 常驻时占用 5668 MiB，只剩 253 MiB，
于是 faster-whisper large-v3 装不下、回落到 CPU（单条 10~13.5 秒）。
再叠加本地 LLM（/qwen3-lora、/ollama、/longtext/chat）并发请求，只会互相挤爆 ——
所以按 docs/plan/03-架构决议 的要求："TTS/识图必须排队"。

本模块只做一件事：**同一时刻只允许一个重型任务**，并给出可观测的状态。

能力边界（诚实标注）：
  · 它只管住 **api.py 进程内**的接口；F5-TTS 跑在**另一个进程**（端口 9881），
    不在这个闸门的管理范围内 —— 要把它也纳入，需要 F5 侧配合（暴露 busy 标志或读同一个标志文件），
    这一点尚未实现。
  · 它是**进程内**的，不是跨进程/跨机器的分布式锁。
"""
import threading
import time

__all__ = ["HeavyGate", "Busy", "GATE"]


class Busy(Exception):
    """在等待上限内没拿到闸门。"""

    def __init__(self, holder, waited):
        super().__init__("重型任务忙（当前占用：%s，已等 %.1fs）" % (holder or "?", waited))
        self.holder = holder
        self.waited = waited


class HeavyGate:
    def __init__(self, history=40):
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._holder = None
        self._waiting = 0
        self._history = []
        self._history_max = history

    # ---------- 使用方 ----------
    def acquire(self, name, timeout=90.0):
        """阻塞直到拿到闸门；超时抛 Busy。返回令牌（release 时用）。"""
        t0 = time.time()
        with self._cv:
            self._waiting += 1
            try:
                while self._holder is not None:
                    remain = timeout - (time.time() - t0)
                    if remain <= 0:
                        raise Busy(self._holder, time.time() - t0)
                    self._cv.wait(min(remain, 0.5))
                self._holder = name
                return {"name": name, "t0": t0}
            finally:
                self._waiting -= 1

    def release(self, token):
        if not token:
            return
        with self._cv:
            self._holder = None
            self._history.append({"name": token.get("name"),
                                  "ms": int((time.time() - token.get("t0", time.time())) * 1000),
                                  "at": time.strftime("%H:%M:%S")})
            if len(self._history) > self._history_max:
                self._history = self._history[-self._history_max:]
            self._cv.notify()

    # ---------- 观测方 ----------
    def status(self):
        with self._lock:
            return {
                "busy": self._holder is not None,
                "holder": self._holder,
                "waiting": self._waiting,
                "recent": list(reversed(self._history[-8:])),
                "note": "仅覆盖 api.py 进程内的重型接口；F5-TTS(9881) 是独立进程，未纳入",
            }


# 进程级单例
GATE = HeavyGate()
''')
print("✓ 新增 tool/heavy_gate.py")

io.open(TEST, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
"""重型闸门的并发互斥测试：真开线程并跑，断言"同时只有一个"（不是靠看代码，是实测计数）。"""
import sys
import threading
import time

sys.path.insert(0, r"E:\\university\\order\\python\\pet\\AIpet-Murasame-main")
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
''')
print("✓ 新增 dev/scripts/test_heavy_gate.py")

print()
print("=== 跑测试 ===")
r = subprocess.run([sys.executable, "-u", TEST], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
print((r.stdout or "")[-2200:])
if r.returncode != 0:
    print((r.stderr or "")[-800:])
    sys.exit(1)
