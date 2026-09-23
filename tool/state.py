# -*- coding: utf-8 -*-
"""她的情绪状态与关系度：心情会随时间衰减，好感度会随互动变化。

为什么要有：以前"情绪"只是一轮回复里的标签（用于立绘），说完就没了 ——
她对主人的态度永远一样。现在多两个长期数值：

    mood      心情 0~100，基线 60；被摸头/被夸会涨，被凶/被冷落会掉，
              而且**随时间向基线回落**（一会儿不理她，气就消了）。
    affinity  好感度 0~100，只会慢慢涨（互动、被摸头、被夸），掉得很慢；
              分档：陌生 / 面熟 / 熟悉 / 亲近 / 离不开。

用法：
    state.feel(+8, "主人摸了头")      # 记一次情绪/关系变化（顺手写日志）
    state.mood_label() / state.affinity_label()
    state.prompt_note()               # 给模型的一句话（"你现在心情…，跟他…"）
    state.summary()                   # 给人看的摘要（菜单/记忆窗口）

存储：pets/<角色>/memory/state.json（带时间戳，重启不丢）。
"""
import json
import os
import time

MOOD_BASE = 60.0            # 心情基线
MOOD_MIN, MOOD_MAX = 0.0, 100.0
# 心情每小时向基线回落多少（越大越"不记仇"）
MOOD_DECAY_PER_HOUR = 6.0
AFFINITY_BASE = 20.0
AFFINITY_MAX = 100.0

_MOOD_LABELS = (
    (85, "开心得不行"), (70, "心情很好"), (55, "心情不错"),
    (40, "还算平静"), (25, "有点低落"), (1, "不太高兴"), (0, "闷闷的，不太想说话"),
)
_AFF_LABELS = (
    (90, "离不开你"), (75, "很亲近"), (55, "熟悉"), (35, "面熟"), (0, "还不太熟"),
)
_state = {"path": None, "data": None}


def _store_path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = os.path.join("memory")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "state.json")


def _now() -> float:
    return time.time()


def _load() -> dict:
    p = _store_path()
    if _state["path"] == p and _state["data"] is not None:
        return _state["data"]
    data = {"mood": MOOD_BASE, "affinity": AFFINITY_BASE, "ts": _now(), "log": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            data.update({k: d.get(k, data[k]) for k in
                         ("mood", "affinity", "ts", "log", "last_talk", "last_speak")})
    except Exception:
        pass
    data["mood"] = float(data.get("mood", MOOD_BASE))
    data["affinity"] = float(data.get("affinity", AFFINITY_BASE))
    _state["path"], _state["data"] = p, data
    _decay(data)
    return data


def _save(data: dict):
    try:
        p = _store_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        print(f"[状态] ⚠ 保存失败: {e}")


def _decay(data: dict):
    """心情随时间向基线回落（离线也算）"""
    try:
        hours = max(0.0, (_now() - float(data.get("ts") or _now())) / 3600.0)
        if hours <= 0:
            return
        m = float(data.get("mood", MOOD_BASE))
        step = MOOD_DECAY_PER_HOUR * hours
        if m > MOOD_BASE:
            m = max(MOOD_BASE, m - step)
        elif m < MOOD_BASE:
            m = min(MOOD_BASE, m + step)
        data["mood"] = m
        data["ts"] = _now()
    except Exception:
        pass


def feel(mood_delta: float = 0.0, affinity_delta: float = 0.0, reason: str = ""):
    """记一次状态变化（心情/好感度都会夹在 0~100 内，并写一行日志）"""
    try:
        d = _load()
        if mood_delta:
            d["mood"] = max(MOOD_MIN, min(MOOD_MAX, float(d.get("mood", MOOD_BASE)) + float(mood_delta)))
        if affinity_delta:
            d["affinity"] = max(0.0, min(AFFINITY_MAX,
                                         float(d.get("affinity", AFFINITY_BASE)) + float(affinity_delta)))
        d["ts"] = _now()
        try:
            lg = list(d.get("log") or [])
            lg.append({"ts": _now(), "mood": mood_delta, "aff": affinity_delta, "why": str(reason)[:40]})
            d["log"] = lg[-80:]
        except Exception:
            pass
        _save(d)
        if reason and (mood_delta or affinity_delta):
            print(f"[状态] {reason}（心情 {mood_delta:+.0f}，好感 {affinity_delta:+.1f} → "
                  f"{d['mood']:.0f}/{d['affinity']:.0f}）")
    except Exception as e:
        print(f"[状态] ⚠ 记录失败: {e}")


def mood() -> float:
    return float(_load().get("mood", MOOD_BASE))


def affinity() -> float:
    return float(_load().get("affinity", AFFINITY_BASE))


def mood_label() -> str:
    m = mood()
    for lo, name in _MOOD_LABELS:
        if m >= lo:
            return name
    return _MOOD_LABELS[-1][1]


def affinity_label() -> str:
    a = affinity()
    for lo, name in _AFF_LABELS:
        if a >= lo:
            return name
    return _AFF_LABELS[-1][1]


def note_talk():
    """记一次"跟主人说过话"（开口时机的评分要用）"""
    try:
        d = _load()
        d["last_talk"] = _now()
        _save(d)
    except Exception:
        pass


def last_talk_ago() -> float:
    """距离上次跟主人说话过了多少秒（没记录返回一个很大的数）"""
    try:
        t = float(_load().get("last_talk") or 0)
        return max(0.0, _now() - t) if t else 1e9
    except Exception:
        return 1e9


def prompt_note() -> str:
    """给模型的"你现在的状态"（影响语气；真人味就靠这个）"""
    try:
        m, a = mood(), affinity()
        bits = [f"心情：{mood_label()}（{m:.0f}/100）",
                f"你和主人的关系：{affinity_label()}（{a:.0f}/100）"]
        if m < 30:
            bits.append("所以语气会偏冷、话少一点，别硬撑热情")
        elif m > 85:
            bits.append("所以语气会更活泼、更黏人一点")
        if a > 80:
            bits.append("对他可以更随意、更亲近，偶尔撒娇")
        elif a < 30:
            bits.append("还比较客气，别太快熟络")
        return "【你此刻的状态（自然流露，不要念出来）】" + "；".join(bits) + "。"
    except Exception:
        return ""


def summary() -> str:
    """给人看的一行摘要"""
    try:
        return (f"心情：{mood_label()}（{mood():.0f}/100）｜"
                f"关系：{affinity_label()}（{affinity():.0f}/100）｜"
                f"上次说话：{_ago_text(last_talk_ago())}")
    except Exception:
        return ""


def _ago_text(sec: float) -> str:
    try:
        if sec >= 1e8:
            return "还没聊过"
        if sec < 60:
            return "刚刚"
        if sec < 3600:
            return f"{int(sec // 60)} 分钟前"
        return f"{sec / 3600:.1f} 小时前"
    except Exception:
        return "?"


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("存储:", _store_path())
    print("摘要:", summary())
    print("注入:", prompt_note())
    print()
    print("模拟：摸头 +6 心情 +0.8 好感")
    feel(6, 0.8, "主人摸了摸头")
    print("摘要:", summary())
    print()
    print("模拟：被说'飞机场' -12 心情 -0.5 好感")
    feel(-12, -0.5, "主人说她是飞机场")
    print("摘要:", summary())
