# -*- coding: utf-8 -*-
"""开口时机：她该不该在这时候说话。

为什么要有
----------
以前是"定时看到屏幕就评论"，容易变成话痨，或者该说的时候不说。现在改成**打分**：
分数到阈值才开口，分数低就安静陪着。

评分因素（都是便宜的本地信息）
----------------------------
    + 屏幕变化大（主人换了事情做，值得搭一句）
    + 很久没跟主人说话了（>10 分钟给分更多）
    + 主人刚回到电脑前（欢迎回来的时机）
    + 心情好 / 关系亲近（更愿意开口）      ← 来自 tool.state
    - 刚说过话（90 秒内基本不说）
    - 主人正在打字 / 她正在回复（绝不插话）
    - 最近一小时已经说过很多次（别话痨）
    - 全屏游戏 / 演示（降权但不完全禁）    ← 来自 tool.perf_guard

配置：`attention_threshold`（默认 3.0）、`attention_enabled`（默认 true）。
活跃度分档（config 的 `autonomy_level`）也生效：quiet 一律不主动开口、active 门槛低 0.8 ——
这一档由 tool.desire 提供；**没有 desire 模块时按 normal 处理**（本仓库尚未移植它）。
"""
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_THRESHOLD = 3.0
_recent = {"speaks": []}          # 最近开口的时间戳
_STORE = {"path": None, "t": 0.0}


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def enabled() -> bool:
    try:
        from tool.config import get_config, as_bool
        return as_bool(get_config("./config.json").get("attention_enabled", "true"), True)
    except Exception:
        return True


def threshold() -> float:
    try:
        from tool.config import get_config
        return float(get_config("./config.json").get("attention_threshold") or DEFAULT_THRESHOLD)
    except Exception:
        return DEFAULT_THRESHOLD


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
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"speaks": _recent["speaks"][-60:]}, f)
        os.replace(tmp, p)
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


def reset_cache():
    """测试/换角色：丢掉进程内缓存"""
    _recent["speaks"] = []
    _STORE["path"], _STORE["t"] = None, 0.0


def score(screen_change_bits=None, user_idle_sec=None, busy=False,
          fullscreen=False, just_greeted=False) -> tuple:
    """算"现在开口合适吗" → (分数, 说明)。分数 ≥ 阈值就该开口。"""
    s = 0.0
    why = []

    # ① 绝对不能开口
    if busy:
        return -99.0, "她正忙/主人正在打字"

    try:
        from tool import state as _st
        since, mood, aff = _st.last_talk_ago(), _st.mood(), _st.affinity()
    except Exception:
        since, mood, aff = 999.0, 60.0, 20.0

    # ② 刚说过话 → 闭嘴
    if since < 90:
        return -5.0, "刚说过话（%.0f 秒前）" % since

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

    # ⑥ 心情/关系（来自 tool.state）
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
        why.append("这一小时已经说了 %d 次" % n)
    elif n >= 3:
        s -= 1.0

    return s, "、".join(why) or "没什么特别的"


def should_speak(threshold_override=None, **kw) -> tuple:
    """要不要开口 → (True/False, 分数, 说明)

    活跃度（config 的 autonomy_level，由 tool.desire 提供；没有 desire 就按 normal）：
      quiet  安静 → 一律不主动开口（只回应主人）
      normal 适中 → 用阈值
      active 活跃 → 门槛低 0.8，更愿意搭话
    """
    if not enabled():
        return False, -99.0, "开口时机总开关关着（attention_enabled）"
    lv = "normal"
    try:
        from tool import desire as _dz
        lv = _dz.level()
    except Exception:
        pass
    if lv == "quiet":
        return False, -99.0, "活跃度=安静（不主动开口）"
    base = float(threshold_override) if threshold_override is not None else threshold()
    if lv == "active":
        base = max(0.5, base - 0.8)
    s, why = score(**kw)
    return (s >= base), s, why


if __name__ == "__main__":
    _say("开关: %s  阈值: %.1f" % (enabled(), threshold()))
    _say("最近一小时开口: %d 次" % speaks_last_hour())
    ok, sc, why = should_speak(just_greeted=True)
    _say("刚回来时：开口=%s 分数=%.2f（%s）" % (ok, sc, why))
    ok2, sc2, why2 = should_speak(busy=True)
    _say("正在打字时：开口=%s 分数=%.2f（%s）" % (ok2, sc2, why2))
