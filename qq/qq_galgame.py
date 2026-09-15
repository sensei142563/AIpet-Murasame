# -*- coding: utf-8 -*-
"""
Galgame 模式（好感度养成玩法，群聊）— 状态存储。

- 开启按人：谁 @ 说「开启galgame模式」就只对谁生效（不会一个人开了全群生效）；
  关闭同理只关闭自己；好感度按「群 × QQ号」分别存储，0~100，初始 50；
- 每轮对话由模型给出 [好感±N] 标记，本模块负责 clamp + 持久化；
- 约会玩法：开启者 @ 提出约会时，按好感度 roll 成功率；
  成功 +15~25 好感、失败 -15~25 好感，每人每群有 60 分钟冷却。
状态文件：data/qq_galgame.json
"""

import os
import json
import time
import random
import threading

from tool.paths import data_path

STATE_FILE = data_path("data", "qq_galgame.json")
_lock = threading.Lock()
_cache = None  # {"groups": {gid: {"members": {uin: {"enabled": bool}}, "affection": {uin: int}, "dates": {uin: ts}}}}

# 约会判定冷却（秒）：同一人在同一群两次约会判定至少间隔 60 分钟（防刷好感）
DATE_COOLDOWN_SEC = 3600
# 约会成功率：基础 30%，每点好感 +0.6%，最高 90%
DATE_BASE_P = 0.30
DATE_PER_AFF = 0.006
DATE_P_CAP = 0.90
# 约会好感变化（大幅，区别于日常每轮 ±10 的小幅）
DATE_DELTA_RANGE = (15, 25)

_DATE_WORDS = ("约会吧", "约会吗", "约我", "约你", "约会去", "来约会", "出去约会", "约个会", "去约会")


def is_date_intent(text) -> bool:
    """判断一条消息是否为约会邀请（Galgame 玩法触发词）"""
    t = (text or "").lower()
    return any(w in t for w in _DATE_WORDS)


def roll_date(affection: int):
    """按好感度 roll 约会结果：返回 (成功?, 好感变化量)"""
    p = min(DATE_P_CAP, DATE_BASE_P + max(0, int(affection)) * DATE_PER_AFF)
    ok = random.random() < p
    lo, hi = DATE_DELTA_RANGE
    delta = random.randint(lo, hi) if ok else -random.randint(lo, hi)
    return ok, delta


def _load():
    global _cache
    if _cache is None:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("groups"), dict):
                    _cache = data
                else:
                    _cache = {"groups": {}}
            else:
                _cache = {"groups": {}}
        except Exception:
            _cache = {"groups": {}}
    return _cache


def _save():
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[QQGalgame] ⚠ 保存状态失败: {e}")


def _group(gid):
    st = _load()
    g = st["groups"].setdefault(str(gid), {"members": {}, "affection": {}})
    return g


def group_enabled(gid) -> bool:
    """兼容旧调用：任意成员开启过即 True（新版按人，见 member_enabled）"""
    try:
        with _lock:
            return bool(_group(gid).get("members")) or bool(_group(gid).get("enabled", False))
    except Exception:
        return False


def member_enabled(gid, uin) -> bool:
    """该成员是否在本群开启 Galgame（按人生效，互不影响）。

    优先看成员自己的开关记录（可单独关闭）；无记录时兼容旧版全群开启
    （历史 enabled=true 的群视为全员默认开启）。"""
    try:
        with _lock:
            g = _group(gid)
            m = (g.get("members") or {}).get(str(uin))
            if m is not None:
                return bool(m.get("enabled", False))
            return bool(g.get("enabled", False))
    except Exception:
        return False


def set_member_enabled(gid, uin, enabled: bool) -> None:
    """开启/关闭 Galgame（只影响该成员自己）"""
    try:
        with _lock:
            g = _group(gid)
            g.setdefault("members", {})[str(uin)] = {"enabled": bool(enabled)}
            _save()
    except Exception as e:
        print(f"[QQGalgame] ⚠ 切换失败: {e}")


def set_group_enabled(gid, enabled: bool) -> None:
    """兼容旧调用：群级开关（新版请用 set_member_enabled 按人）"""
    try:
        with _lock:
            _group(gid)["enabled"] = bool(enabled)
            _save()
    except Exception as e:
        print(f"[QQGalgame] ⚠ 切换失败: {e}")


def get_affection(gid, uin) -> int:
    """读取某群某人的好感度（默认 50）。
    白名单主人永远 100（主人不参与好感养成）。"""
    try:
        from qq.qq_memory import is_owner
        if is_owner(uin):
            return 100
    except Exception:
        pass
    try:
        with _lock:
            g = _group(gid)
            try:
                return max(0, min(100, int(g["affection"].get(str(uin), 50))))
            except Exception:
                return 50
    except Exception:
        return 50


def apply_change(gid, uin, delta, big=False) -> int:
    """应用好感度变化（clamp 0~100），返回新好感度。
    白名单主人的好感度恒定 100，不参与增减。
    big=True 用于约会等大额结算（每轮 ±30 上限）；默认日常 ±10/+(-20)。"""
    try:
        from qq.qq_memory import is_owner
        if is_owner(uin):
            return 100
    except Exception:
        pass
    try:
        if big:
            delta = max(-30, min(30, int(delta)))
        else:
            delta = max(-20, min(10, int(delta)))
        with _lock:
            g = _group(gid)
            cur = 50
            try:
                cur = int(g["affection"].get(str(uin), 50))
            except Exception:
                pass
            new = max(0, min(100, cur + delta))
            g["affection"][str(uin)] = new
            _save()
            return new
    except Exception as e:
        print(f"[QQGalgame] ⚠ 好感度更新失败: {e}")
        return 50


def date_available(gid, uin) -> bool:
    """该成员是否已过约会冷却（可再次发起约会）"""
    try:
        with _lock:
            g = _group(gid)
            ts = g.get("dates", {}).get(str(uin), 0)
            return time.time() - ts >= DATE_COOLDOWN_SEC
    except Exception:
        return True


def mark_date_used(gid, uin) -> None:
    """记录一次约会判定时间（进入冷却）"""
    try:
        with _lock:
            g = _group(gid)
            g.setdefault("dates", {})[str(uin)] = time.time()
            _save()
    except Exception:
        pass
