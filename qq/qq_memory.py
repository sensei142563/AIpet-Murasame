# -*- coding: utf-8 -*-
"""
QQ 记忆分仓 — 让不同 QQ 号/群拥有独立记忆，互不串味。

路由规则：
- 私聊来自「预设大号」(config.qq_owner_id)
    → 维持现有逻辑：读/写 data/long_history.json + 同步 history.json（与桌宠共享）
- 私聊来自其他 QQ 号
    → 读/写 data/qq_memory/<QQ号>.json（12 轮长文本逻辑，不写短文本）
- 群聊
    → 读/写 data/qq_memory/group_<群号>.json（12 轮长文本逻辑，不写短文本）

分仓文件格式与 long_history.json 完全一致（含 priority 字段），
由本模块统一提供 load/save 接口。
"""

import os
import json
import time
import threading

from tool.paths import data_path


def _active_qq_memory_dir() -> str:
    """当前角色的 QQ 分仓记忆目录（pets/<角色>/memory/qq），失败回退全局 data/qq_memory"""
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
        if d:
            return os.path.join(d, "qq")
    except Exception:
        pass
    return data_path("data", "qq_memory")


# 向后兼容：PCL 记忆管理页引用（初始为当前角色目录）
MEMORY_DIR = _active_qq_memory_dir()

# 分仓记忆线程锁
_MEMORY_LOCKS = {}
_MEMORY_GLOBAL_LOCK = threading.Lock()


def _load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[QQMemory] 读取 {os.path.basename(path)} 失败: {e}")
    return {}


def _save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[QQMemory] 写入 {os.path.basename(path)} 失败: {e}")


def _get_lock(key: str):
    """每个记忆文件一把锁，避免并发写冲突"""
    with _MEMORY_GLOBAL_LOCK:
        if key not in _MEMORY_LOCKS:
            _MEMORY_LOCKS[key] = threading.RLock()
        return _MEMORY_LOCKS[key]


def is_owner(user_id):
    """判断某个 QQ 号是否为「预设大号」（共享记忆）"""
    if not user_id:
        return False
    try:
        from qq.qq_config import load_config
        cfg = load_config()
        owner = str(cfg.get("qq_owner_id", "")).strip()
        if not owner:
            return False
        return str(user_id) == owner
    except Exception:
        return False


def resolve_memory_path(session_key: str) -> str:
    """
    根据 session_key 解析记忆文件路径。

    session_key 格式：
    - "private_<QQ号>"     → 私聊（可能是大号或其他人）
    - "group_<群号>"       → 群聊

    "private_<大号>" 返回 None → 表示走共享记忆（long_history.json）。
    """
    if not session_key:
        return None

    mem_dir = _active_qq_memory_dir()

    # 私聊
    if session_key.startswith("private_"):
        user_id = session_key.split("_", 1)[1]
        if is_owner(user_id):
            return None  # 大号 → 共享记忆
        return os.path.join(mem_dir, f"{user_id}.json")

    # 群聊
    if session_key.startswith("group_"):
        group_id = session_key.split("_", 1)[1]
        return os.path.join(mem_dir, f"group_{group_id}.json")

    return None


def load_memory(session_key: str, max_turns: int = 12):
    """
    读取某会话的记忆。
    返回: [{"role": ..., "content": ..., "priority": ...}, ...] 最近 max_turns 轮
    - 大号私聊 → 走 long_history.json（与桌宠共享）
    - 其他 → 走分仓文件
    """
    path = resolve_memory_path(session_key)

    # 大号 → 共享记忆
    if path is None:
        from longtext.longtext_history import load_long_history
        return load_long_history(max_turns=max_turns)

    # 分仓 → 独立文件
    lock = _get_lock(session_key)
    with lock:
        data = _load_json(path)
    if isinstance(data, list):  # 兼容 PCL 清空旧 bug 写出的裸列表
        data = {"history": data}
    history = data.get("history", []) or []
    limit = max_turns * 2
    return history[-limit:] if len(history) > limit else history


def save_memory(session_key: str, messages: list, max_turns: int = 12, sync_short: bool = True):
    """
    保存某会话的记忆。

    - 大号私聊：写入 long_history.json + 可选同步 history.json（sync_short 默认 True）
    - 其他：写入分仓文件，不写 short_history（sync_short 被忽略）
    """
    path = resolve_memory_path(session_key)

    # 大号 → 共享记忆（维持现有逻辑）
    if path is None:
        from longtext.longtext_history import save_long_history, sync_to_short_history
        save_long_history(messages, max_turns=max_turns)
        if sync_short:
            try:
                sync_to_short_history(messages)
            except Exception:
                pass
        return

    # 分仓 → 独立文件（不写短文本记忆）
    lock = _get_lock(session_key)
    with lock:
        data = _load_json(path)
        history = data.get("history", []) or []

        # 构造条目（保留 priority）
        for msg in messages:
            entry = {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp") or time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if msg.get("priority"):
                entry["priority"] = msg["priority"]
            history.append(entry)

        # 只保留最近 max_turns 轮
        limit = max_turns * 2
        if len(history) > limit:
            history = history[-limit:]

        data["history"] = history
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_json(path, data)


def demote_high_priority(session_key: str):
    """
    将某会话中 priority=high 的消息降为 low（识别观察仅一轮高权重）。
    - 大号：调用 long_history.demote_high_priority()
    - 分仓：文件内降权
    """
    path = resolve_memory_path(session_key)

    if path is None:
        from longtext.longtext_history import demote_high_priority as _demote
        try:
            _demote()
        except Exception:
            pass
        return

    lock = _get_lock(session_key)
    with lock:
        data = _load_json(path)
        history = data.get("history", []) or []
        changed = False
        for msg in history:
            if isinstance(msg, dict) and msg.get("priority") == "high":
                msg["priority"] = "low"
                changed = True
        if changed:
            data["history"] = history
            data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save_json(path, data)