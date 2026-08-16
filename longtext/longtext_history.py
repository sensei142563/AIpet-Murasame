# -*- coding: utf-8 -*-
"""
长文本模式专属记忆系统（多桌宠隔离版）。

- 每个角色独立记忆，存储在 pets/<角色>/memory/ 下：
  - long_history.json: 长文本模式完整对话（高权重，最近 N 轮）
  - history.json:      同步写入短文本记忆（普通权重）

- 旧数据迁移：升级后首次使用新路径时，若旧 data/long_history.json 有内容
  且新路径为空，自动迁移（只迁移一次，迁移后旧文件保留但不读取）。

优先级机制（priority 字段）：
- high: 识别（截图/摄像头）触发的临时观察，仅在下一轮对话有高权重
- low:  该轮对话结束后降权，不再注入 API（权重≈0）
- 无:   普通对话消息
"""

import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 旧全局记忆路径（用于迁移）
OLD_LONG_HISTORY_FILE = BASE_DIR / "data" / "long_history.json"
OLD_SHORT_HISTORY_FILE = BASE_DIR / "data" / "history.json"


def _memory_dir() -> Path:
    """当前角色的记忆目录（pets/<角色>/memory/），失败则回退全局 data/"""
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
        if d:
            return Path(d)
    except Exception:
        pass
    return BASE_DIR / "data"


def _long_history_file() -> Path:
    return _memory_dir() / "long_history.json"


def _short_history_file() -> Path:
    return _memory_dir() / "history.json"


def _migrate_if_needed():
    """旧数据迁移：新路径为空且旧路径有数据时，迁移一次。"""
    new_long = _long_history_file()
    try:
        # 新路径已有数据 → 无需迁移
        if new_long.exists() and new_long.stat().st_size > 0:
            return
        # 旧路径有数据 → 迁移
        if OLD_LONG_HISTORY_FILE.exists() and OLD_LONG_HISTORY_FILE.stat().st_size > 0:
            data = _load_json(OLD_LONG_HISTORY_FILE, {})
            if data.get("history"):
                _save_json(new_long, data)
                print(f"[LongHistory] 已迁移旧记忆到角色目录: {new_long}")
    except Exception as e:
        print(f"[LongHistory] 迁移旧记忆失败: {e}")


def _load_json(path, default=None):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            # 兼容历史 bug：PCL 清空曾把文件写成裸列表 → 归一化为 {"history": [...]}
            if isinstance(data, list):
                data = {"history": data}
            return data
    except Exception:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                data = {"history": data}
            return data
        except Exception as e:
            print(f"[LongHistory] 读取 {path.name} 失败: {e}")
    return default if default is not None else {}


def _save_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LongHistory] 写入 {path.name} 失败: {e}")


def _make_entry(msg):
    """构造消息条目，保留 priority 字段（若有）"""
    entry = {
        "role": msg.get("role", "user"),
        "content": msg.get("content", ""),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if msg.get("priority"):
        entry["priority"] = msg["priority"]
    return entry


def load_long_history(max_turns=12):
    """
    读取长文本记忆（当前角色）。
    返回: [{"role": ..., "content": ..., "priority": ...}, ...] 最近 max_turns 轮
    注意：不在此处过滤 priority，由调用方决定如何处理。
    """
    _migrate_if_needed()
    data = _load_json(_long_history_file(), {})
    history = data.get("history", [])
    limit = max_turns * 2
    return history[-limit:] if len(history) > limit else history


def save_long_history(messages, max_turns=12):
    """
    保存长文本记忆（当前角色，只追加）。
    messages: [{"role": ..., "content": ...}, ...] 本次新增的消息
    """
    _migrate_if_needed()
    path = _long_history_file()
    data = _load_json(path, {})
    history = data.get("history", [])

    for msg in messages:
        history.append(_make_entry(msg))

    limit = max_turns * 2
    if len(history) > limit:
        history = history[-limit:]

    data["history"] = history
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_json(path, data)


def sync_to_short_history(messages):
    """
    将长文本模式对话同步写入短文本模式记忆（当前角色）history.json。
    messages: [{"role": ..., "content": ...}, ...]
    """
    path = _short_history_file()
    data = _load_json(path, {})
    history = data.get("history", [])
    if not isinstance(history, list):
        history = []

    for msg in messages:
        history.append(_make_entry(msg))

    data["history"] = history
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_json(path, data)


def demote_high_priority():
    """
    将当前角色 long_history.json 中所有 priority=high 的消息降为 low。
    在每轮对话结束后调用——识别观察仅在下一轮有高权重。
    """
    path = _long_history_file()
    data = _load_json(path, {})
    history = data.get("history", [])
    changed = False
    for msg in history:
        if isinstance(msg, dict) and msg.get("priority") == "high":
            msg["priority"] = "low"
            changed = True
    if changed:
        data["history"] = history
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _save_json(path, data)


def clear_long_history():
    """清空当前角色长文本记忆"""
    _save_json(_long_history_file(), {"history": [], "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")})