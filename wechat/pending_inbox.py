# -*- coding: utf-8 -*-
"""
微信待处理收件箱（防丢消息，Android PendingInbox 的 Python 移植）。

问题背景：长轮询收包若「先推游标再处理」，处理期间进程崩溃/断电 → 游标已推进，
这批消息永远收不回来。桌面常开挂机场景最怕这个。

做法（at-least-once：宁可重复，不可丢）：
1. 收包线程：get_updates → 每条消息先落 pending.json → 再推游标 → 后分发处理
2. 调度线程：回复「发送成功」才按 id 删除对应 pending 条目
3. 进程启动进入轮询前：pending 非空 → 先全部补处理（重复回复的风险远小于丢消息）

可靠性细节：
- add() 落盘失败返回 None（不返回假 id）——调用侧必须“落盘成功才推游标”，
  失败则不推，让服务端下轮重发，杜绝“以为存了其实没存”的假 at-least-once。
- 条目带 added_ts（unix 秒）：补处理时自动清理「太老」条目（如媒体 CDN 已过期的
  图片消息永远补不回来，留着只会无限重试 → 超过 TTL 自动丢弃，防收件箱膨胀）。

存储：data/wechat_pending.json（原子写 tmp + os.replace，防写半截损坏）。
"""
import os
import json
import time
import uuid
import threading

from tool.paths import data_path

PENDING_FILE = data_path("data", "wechat_pending.json")
# 防膨胀上限：超过后丢弃最旧条目（仅在消息长期无法回复时触发，属异常保护）
MAX_PENDING = 500
# 条目最长保留时间（秒）：媒体 CDN 链接约 24h 过期，超过该时间补拉也无意义
PENDING_TTL = 48 * 3600

_lock = threading.RLock()


def _now_ts() -> float:
    return time.time()


def _load():
    try:
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            items = d.get("pending", []) if isinstance(d, dict) else []
            return [i for i in items if isinstance(i, dict)]
    except Exception as e:
        print(f"[PendingInbox] ⚠ 读取失败（可能损坏，重置为空）: {e}")
    return []


def _save(items) -> bool:
    """原子写。成功返回 True；失败返回 False（不吞异常隐藏问题）。"""
    try:
        os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
        tmp = PENDING_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"pending": items}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, PENDING_FILE)  # 原子替换，防写半截损坏
        return True
    except Exception as e:
        print(f"[PendingInbox] ⚠ 写入失败（调用侧将不推游标）: {e}")
        return False


def _drop_expired(items) -> list:
    """移除超 TTL 的旧条目（媒体 CDN 过期后补拉无意义，防无限膨胀）"""
    now = _now_ts()
    kept = []
    for i in items:
        ts = i.get("added_ts") or 0
        if now - float(ts) > PENDING_TTL:
            print(f"[PendingInbox] 🧹 丢弃超 {PENDING_TTL // 3600}h 的旧条目 id={i.get('id', '')}")
            continue
        kept.append(i)
    return kept


def add(msg):
    """将一条原始消息落收件箱，返回 pending id；落盘失败返回 None（调用侧勿推游标）。"""
    with _lock:
        items = _load()
        pid = str(uuid.uuid4())
        items.append({
            "id": pid,
            "msg": msg,
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "added_ts": _now_ts(),
        })
        # 先清过期条目再判上限，减少误丢
        items = _drop_expired(items)
        # 防膨胀：超过上限丢弃最旧（正常流程不会触发）
        if len(items) > MAX_PENDING:
            dropped = items[: len(items) - MAX_PENDING]
            print(f"[PendingInbox] ⚠ pending 超过 {MAX_PENDING} 条，丢弃最旧 {len(dropped)} 条"
                  f"（消息持续无法回复？请检查 -14/网络/LLM 错误）")
            items = items[-MAX_PENDING:]
        if not _save(items):
            return None  # 落盘失败：调用侧不要推进游标
        return pid


def remove(pid):
    """回复发送成功后删除对应条目（幂等：不存在也不报错）"""
    if not pid:
        return
    with _lock:
        items = _load()
        before = len(items)
        items = [i for i in items if i.get("id") != pid]
        if len(items) != before:
            _save(items)


def all_items():
    """返回 [(pid, msg), ...] 快照（进程启动补处理用）；顺带清理过期条目并落盘"""
    with _lock:
        items = _load()
        cleaned = _drop_expired(items)
        if len(cleaned) != len(items):
            _save(cleaned)  # 持久清理，避免下次 count()/add() 又读到旧条目
        return [(i.get("id", ""), i.get("msg", {})) for i in cleaned]


def clear():
    """清空收件箱（仅供调试/彻底放弃时用）"""
    with _lock:
        _save([])


def count() -> int:
    with _lock:
        return len(_load())
