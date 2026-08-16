# -*- coding: utf-8 -*-
"""
QQ 消息调度器 — 统一 FIFO 队列 + 串行处理 + 会话合并。

解决两个问题：
1. 离线消息补推：NapCat 连接后自动补推离线消息事件，全部入队按到达顺序处理
2. 多人同时聊不乱不卡：全局串行队列，一次只处理一条会话；同一会话 1.5 秒内
   多条消息合并为一次回复（避免连发 5 条被回 5 次的割裂感）

使用方式：
    scheduler = MessageScheduler(handler)
    scheduler.enqueue({
        "session_key": "private_<QQ号>" 或 "group_<群号>",
        "text": "纯文本内容",
        "user_id": QQ号,
        "nickname": 昵称,
        "group_id": 群号 or None,
        "vision_desc": 图片识别结果 or None,
        "arrive_time": time.time(),
    })

handler 签名：
    def handle_message(msg: dict):
        # msg 含合并后的完整内容
        pass
"""

import time
import random
import threading
from collections import deque

# 群聊合并窗口（秒）——群里 @ 需较快回复，不宜等太久
GROUP_MERGE_SECONDS = 1.5

# 私聊合并窗口范围（秒）——真人发消息是断断续续的，等一小段时间收集后续消息
PRIVATE_MERGE_RANGE = (1.5, 5.0)


class MessageScheduler:
    """全局消息调度器：FIFO 队列 + 串行处理 + 会话合并"""

    def __init__(self, handler, merge_window=None):
        """
        handler: 处理单条消息的回调函数 (msg: dict) -> None
                 由 bridge 注入，负责调用 chat_once + 发送回复
        merge_window: 兼容旧参数（已废弃，改为按会话类型动态计算）
        """
        self._handler = handler
        self._merge_window = merge_window  # 兼容旧调用（不再直接使用）
        self._queue = deque()
        self._cv = threading.Condition()
        self._running = True
        self._processing = False  # 是否正在处理某条消息（合并判断用）

        self._thread = threading.Thread(target=self._run, daemon=True, name="QQScheduler")
        self._thread.start()

    def _get_merge_window(self, session_key) -> float:
        """
        根据会话类型返回合并等待窗口（秒）：
        - 私聊（private_*）：随机 1.5~5 秒，给真人留出继续打字的时间
        - 群聊（group_*）：  固定 1.5 秒，群里 @ 需较快回复
        """
        if str(session_key).startswith("private_"):
            return random.uniform(*PRIVATE_MERGE_RANGE)
        return GROUP_MERGE_SECONDS

    def enqueue(self, msg: dict):
        """消息入队（实时事件或离线补推都走这里）"""
        msg.setdefault("arrive_time", time.time())
        with self._cv:
            self._queue.append(msg)
            self._cv.notify()

    def _run(self):
        """调度主循环：串行取出消息 → 合并同一会话 → 调用处理器"""
        while self._running:
            msg = self._take_next_with_merge()
            if msg is None:
                continue
            try:
                self._handler(msg)
            except Exception as e:
                import traceback
                print(f"[QQScheduler] ⚠ 处理消息异常: {e}")
                traceback.print_exc()

    def _take_next_with_merge(self):
        """
        取出一条（或多条合并的）消息。
        - 阻塞直到队列非空
        - 取出后等待 merge_window 秒，允许同一会话的新消息合并进来
        - 返回合并后的 dict（含 merged_msgs 字段）
        """
        with self._cv:
            # 1. 等待队列非空
            while not self._queue and self._running:
                self._cv.wait(0.5)
            if not self._running and not self._queue:
                return None
            if not self._queue:
                return None

            # 2. 取出最早的一条
            first = self._queue.popleft()
            first["merged_msgs"] = [first]

        # 3. 合并窗口：等待同会话新消息
        #    - 私聊：随机 1.5~5 秒（给人留出继续打字的时间）
        #    - 群聊：固定 1.5 秒（群里 @ 需较快回复）
        #    用轮询检查，避免持有锁等待（保证其他线程能入队）
        merge_window = self._get_merge_window(first["session_key"])
        deadline = time.time() + merge_window
        while time.time() < deadline:
            with self._cv:
                # 找队列中同 session 的消息
                same = None
                same_idx = None
                for i, m in enumerate(self._queue):
                    if m["session_key"] == first["session_key"]:
                        same = m
                        same_idx = i
                        break
                if same is not None:
                    # 合并：从 deque 中按索引移除（deque 用 list 转换删除）
                    items = list(self._queue)
                    if 0 <= same_idx < len(items):
                        extra = items.pop(same_idx)
                        self._queue = deque(items)
                        first["merged_msgs"].append(extra)
                        # 重置合并窗口（有连续对话就继续等）
                        deadline = time.time() + merge_window
            time.sleep(0.2)

        # 4. 合并后的文本（多条消息用换行拼接）
        if len(first["merged_msgs"]) > 1:
            texts = [m.get("text", "").strip() for m in first["merged_msgs"]]
            first["text"] = "\n".join(t for t in texts if t)
            print(f"[QQScheduler] 合并 {len(first['merged_msgs'])} 条消息: {first['text'][:60]}...")

        return first

    def stop(self):
        """停止调度器"""
        self._running = False
        with self._cv:
            self._cv.notify_all()