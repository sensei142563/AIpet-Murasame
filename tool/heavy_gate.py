# -*- coding: utf-8 -*-
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
