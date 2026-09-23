# -*- coding: utf-8 -*-
"""开口时机：她该不该在这时候说话（参考 Miru 的 AttentionEngine 思路）。

以前是"定时看到屏幕就评论"，容易变成话痨或者该说的时候不说。
现在改成打分的：分数到阈值才开口，分数低就安静陪着。

评分因素（都是便宜的本地信息）：
    + 屏幕变化大（说明主人换了事情做，值得搭一句）
    + 很久没跟主人说话了（超过 10 分钟给更多分）
    + 心情好 / 关系亲近（更愿意开口）
    + 主人刚回到电脑前（欢迎回来的时机）
    - 刚说过话（90 秒内基本不说）
    - 主人正在打字 / 她正在回复（绝不插话）
    - 最近一小时内已经说过很多次（别话痨）
    - 全屏游戏/演示（稍微降权，但不完全禁）

配置（config.json，可调）：attention_threshold 默认 3.0。
"""
import json
import os
import time

DEFAULT_THRESHOLD = 3.0
_recent = {"speaks": []}          # 最近开口的时间戳
_STORE = {"path": None, "t": 0.0}


def _cfg(key, default):
    try:
        from tool.config import get_config
        v = get_config("./config.json").get(key, default)
        return type(default)(v) if not isinstance(default, bool) else str(v).lower() in ("true", "1", "on", "yes")
    except Exception:
        return default


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "attention.json")


def _load():
    """开口记录持久化（重启也算数，别一重启就话痨）"""
    try:
        p = _path()
        if _STORE["path"] == p and time.time() - float(_STORE["t"] or 0) < 30:
            return
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("speaks"), list):
            _recent["speaks"] = [float(x) for x in d["speaks"]][-60:]
        _STORE["path"], _STORE["t"] = p, time.time()
    except Exception:
        pass


def _save():
    try:
        p = _path()
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"speaks": _recent["speaks"][-60:]}, f)
    except Exception:
        pass


def note_spoke():
    """记一次"她开口了"（打分时用来克制自己）"""
    _load()
    _recent["speaks"].append(time.time())
    _save()


def speaks_last_hour() -> int:
    _load()
    t = time.time()
    return len([x for x in _recent["speaks"] if t - x < 3600])


def score(screen_change_bits=None, user_idle_sec=None, busy=False,
          fullscreen=False, just_greeted=False) -> tuple:
    """算"现在开口合适吗" → (分数, 说明)。分数 ≥ 阈值就该开口。"""
    s = 0.0
    why = []

    # ① 绝对不能开口的情况
    if busy:
        return -99.0, "她正忙/主人正在打字"
    try:
        from tool import state as _st
        since = _st.last_talk_ago()
        mood = _st.mood()
        aff = _st.affinity()
    except Exception:
        since, mood, aff = 999.0, 60.0, 20.0

    # ② 刚说过话 → 闭嘴
    if since < 90:
        return -5.0, f"刚说过话（{since:.0f} 秒前）"

    # ③ 屏幕变化
    try:
        if screen_change_bits is not None:
            if screen_change_bits >= 25:
                s += 2.5
                why.append("屏幕变化明显")
            elif screen_change_bits >= 12:
                s += 1.0
                why.append("屏幕有点变化")
            else:
                s -= 1.5
                why.append("屏幕没怎么变")
    except Exception:
        pass

    # ④ 时间：越久没说话越该搭一句
    if since > 1800:
        s += 2.5
        why.append("半小时没理他了")
    elif since > 600:
        s += 1.5
        why.append("十分钟没说话了")
    elif since > 300:
        s += 0.5

    # ⑤ 主人状态
    if user_idle_sec is not None:
        if user_idle_sec > 900:
            s += 1.0
            why.append("他好像离开了一会儿")
        elif user_idle_sec < 20:
            s += 0.5                # 刚回来
    if just_greeted:
        s += 2.0
        why.append("他刚回到电脑前")
    if fullscreen:
        s -= 1.0                    # 打游戏时少打扰（但不完全禁）

    # ⑥ 心情/关系
    s += (mood - 60.0) / 40.0       # ±1 左右
    s += (aff - 20.0) / 60.0        # 0~1.3
    if mood < 30:
        s -= 0.5
        why.append("心情不太好")
    if aff > 75:
        s += 0.5

    # ⑦ 别话痨：一小时内说得越多越克制
    n = speaks_last_hour()
    if n >= 6:
        s -= 2.5
        why.append(f"这一小时已经说了 {n} 次")
    elif n >= 3:
        s -= 1.0

    return s, "、".join(why) or "没什么特别的"


def should_speak(threshold=None, **kw) -> tuple:
    """要不要开口 → (True/False, 分数, 说明)

    活跃度（config 的 autonomy_level）也在这里生效：
      quiet  安静 → 一律不主动开口（只回应主人）
      normal 适中 → 用阈值
      active 活跃 → 门槛低 0.8，更愿意搭话
    """
    lv = "normal"
    try:
        from tool import desire as _dz
        lv = _dz.level()
    except Exception:
        pass
    if lv == "quiet":
        return False, -99.0, "活跃度=安静（不主动开口）"
    base = float(_cfg("attention_threshold", DEFAULT_THRESHOLD))
    if threshold is not None:
        base = float(threshold)
    if lv == "active":
        base = max(0.5, base - 0.8)
    s, why = score(**kw)
    return (s >= base), s, why


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("阈值:", _cfg("attention_threshold", DEFAULT_THRESHOLD))
    cases = [
        ("屏幕大变化 + 一小时没说话", dict(screen_change_bits=40, user_idle_sec=120)),
        ("屏幕没变 + 刚说过", dict(screen_change_bits=3, user_idle_sec=5)),
        ("她正忙", dict(busy=True)),
        ("全屏游戏 + 屏幕小变化", dict(screen_change_bits=14, fullscreen=True, user_idle_sec=100)),
        ("主人刚回来", dict(screen_change_bits=30, just_greeted=True)),
    ]
    for name, kw in cases:
        ok, s, why = should_speak(**kw)
        print("  %-26s → %-5s 分数 %5.1f（%s）" % (name, "开口" if ok else "安静", s, why))
    print()
    print("这一小时开过口几次:", speaks_last_hour())
