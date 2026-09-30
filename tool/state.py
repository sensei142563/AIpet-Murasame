# -*- coding: utf-8 -*-
"""她的长期状态：心情会随时间衰减，好感度会随互动变化。

为什么要有
----------
以前"情绪"只是**一轮回复里的标签**（用来挑立绘/语气），说完就没了 —— 她对主人的态度
永远一样。现在多两个**长期数值**（存盘、重启不丢、离线也会衰减）：

    mood      心情 0~100，基线 60；被摸头/被夸会涨，被凶/被冷落会掉，
              而且随时间**向基线回落**（一会儿不理她，气就消了）。
    affinity  好感度 0~100，基线 20，只会慢慢涨（互动/摸头/被夸），掉得极慢；
              分档：还不太熟 / 面熟 / 熟悉 / 很亲近 / 离不开你。

用法
----
    state.feel(mood_delta=+8, affinity_delta=+0.5, reason="被摸头")
    state.mood_label() / state.affinity_label()
    state.prompt_note()      # 塞进系统提示词的一句话（"你此刻的状态…"）
    state.summary()          # 给人看的一行摘要（状态窗/记忆页）
    state.note_talk() / state.last_talk_ago()   # 开口时机评分要用

存储：`pets/<角色>/memory/state.json`（走 pet_registry.get_memory_dir，原子替换写入）。

⚠ 与 QQ 那套「好感度」区分
--------------------------
`qq/qq_galgame.py` 的是**群聊 galgame 玩法**的好感度（按「群 × QQ号」分别存、初始 50、
由模型输出 [好感±N] 标记驱动）。这里是**桌宠与主人**之间的长期关系，两者互不影响。
"""
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MOOD_BASE = 60.0            # 心情基线
MOOD_MIN, MOOD_MAX = 0.0, 100.0
MOOD_DECAY_PER_HOUR = 6.0   # 心情每小时向基线回落多少（越大越"不记仇"）
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


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


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
            # ⚠ 这里**不能**写 `d.get(k, data[k])`：键表里有 last_talk / last_speak，
            #   它们不在初始 data 里 → 取默认值时 KeyError → 被下面 except 吞掉 →
            #   整个读盘结果被丢弃（存了等于没存，每次启动都回到默认值）。
            #   这是从远端那条线照搬过来的真 bug，自测抓到的。
            for _k in ("mood", "affinity", "ts", "log", "last_talk", "last_speak"):
                if _k in d:
                    data[_k] = d[_k]
    except Exception:
        pass
    try:
        data["mood"] = float(data.get("mood", MOOD_BASE))
        data["affinity"] = float(data.get("affinity", AFFINITY_BASE))
    except Exception:
        data["mood"], data["affinity"] = MOOD_BASE, AFFINITY_BASE
    _state["path"], _state["data"] = p, data
    _decay(data)
    return data


def _save(data: dict):
    try:
        p = _store_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)          # 原子替换：不会写坏旧文件
    except Exception as e:
        _say("[状态] ⚠ 保存失败: %s" % e)


def _decay(data: dict):
    """心情随时间向基线回落（**离线那段时间也算**：按时间戳补算）"""
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
    """记一次状态变化（都夹在 0~100 内，并写一行日志，最多留 80 条）"""
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
            lg.append({"ts": _now(), "mood": mood_delta, "aff": affinity_delta,
                       "why": str(reason)[:40]})
            d["log"] = lg[-80:]
        except Exception:
            pass
        _save(d)
        if reason and (mood_delta or affinity_delta):
            _say("[状态] %s（心情 %+.0f，好感 %+.1f → %.0f/%.0f）"
                 % (reason, mood_delta, affinity_delta, d["mood"], d["affinity"]))
    except Exception as e:
        _say("[状态] ⚠ 记录失败: %s" % e)


def mood() -> float:
    return float(_load().get("mood", MOOD_BASE))


def _talk_count() -> int:
    """真实对话条数（**现役**角色的 memory/history.json 里的 history 列表）。读不到就 0。

    ⚠ codex 复审 P2：原来读的是 `data/history.json` —— 那是**旧版遗留**文件（迁移时写过一次，
    见 classes/murasame_class.py 的迁移段），现役记录在 `pets/<角色>/memory/history.json`。
    读错文件会让 affinity_floor() 的「真实对话条数」项对老用户偏小、对新装恒为 0，
    与 docstring 说的"按真实相处证据"不符。现在优先读现役文件，读不到才退回旧文件。
    """
    import json as _json
    import os as _os
    cands = []
    try:
        from pets.pet_registry import get_memory_dir
        cands.append(_os.path.join(get_memory_dir(), "history.json"))
    except Exception:
        pass
    cands.append(_os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "data", "history.json"))          # 旧版遗留，仅兜底
    for p in cands:
        try:
            with open(p, encoding="utf-8") as f:
                d = _json.load(f)
            h = d.get("history") if isinstance(d, dict) else d
            if isinstance(h, list) and h:
                return int(len(h))
        except Exception:
            continue
    return 0


def affinity_floor() -> float:
    """按**真实相处证据**给关系一个下限。

    用户 2026-09-30：提示词里早就是老夫老妻了（甚至多次亲密），状态却写「关系 20.4 / 还不太熟」——
    因为 AFFINITY_BASE=20、每次互动只 +0.4、还会随时间回落，100 天也涨不上去。
    提示词不动（用户要求），那就让**状态**去对齐事实：
      · 在一起天数 × 0.7（100 天 → 70）
      · 真实对话条数 × 0.03（封顶 2000 条 → 最多 +60）
      · 合计夹在 [20, 88]：新用户（1 天、没聊过）仍是 20，体感不变；
        老用户能到「很亲近」档（75+），但"离不开你"（90+）仍要靠真实互动攒
    """
    try:
        days = 1
        try:
            from tool import care as _care
            days = max(1, int(_care.companion_days()))
        except Exception:
            pass
        msgs = _talk_count()
        return max(AFFINITY_BASE, min(88.0, days * 0.75 + min(2000, msgs) * 0.03))
    except Exception:
        return AFFINITY_BASE


def affinity() -> float:
    """当前关系值。**读的时候不低于 affinity_floor()**，并把抬上去的值落盘，

    这样状态窗/摘要/提示词看到的是同一个数（不会这处显示 20、那处显示 79）。
    """
    try:
        d = _load()
        cur = float(d.get("affinity", AFFINITY_BASE))
        floor = affinity_floor()
        if floor > cur:
            d["affinity"] = floor
            _save(d)
            _say("[状态] 关系下限生效：%.1f → %.1f（按在一起天数与真实对话条数）"
                 % (cur, floor))
            return floor
        return cur
    except Exception:
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
    """记一次"跟主人说过话"（开口时机/沉默时长的评分要用）"""
    try:
        d = _load()
        d["last_talk"] = _now()
        _save(d)
    except Exception:
        pass


def last_talk_ago() -> float:
    """距离上次跟主人说话过了多少秒（没记录过返回一个很大的数）"""
    try:
        t = float(_load().get("last_talk") or 0)
        return max(0.0, _now() - t) if t else 1e9
    except Exception:
        return 1e9


def prompt_note() -> str:
    """给模型的「你现在的状态」（影响语气；真人味就靠这个）"""
    try:
        m, a = mood(), affinity()
        bits = ["心情：%s（%.0f/100）" % (mood_label(), m),
                "你和主人的关系：%s（%.0f/100）" % (affinity_label(), a)]
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


def _ago_text(sec: float) -> str:
    try:
        if sec >= 1e8:
            return "还没聊过"
        if sec < 60:
            return "刚刚"
        if sec < 3600:
            return "%d 分钟前" % int(sec // 60)
        if sec < 86400:
            return "%d 小时前" % int(sec // 3600)
        return "%d 天前" % int(sec // 86400)
    except Exception:
        return "?"


def summary() -> str:
    """给人看的一行摘要（状态窗/记忆页/自检）"""
    try:
        return ("心情:%s（%.0f/100）｜关系:%s（%.0f/100）｜上次说话:%s"
                % (mood_label(), mood(), affinity_label(), affinity(),
                   _ago_text(last_talk_ago())))
    except Exception:
        return ""


def reset_cache():
    """换角色 / 测试用：丢掉进程内缓存（下次重新读盘）"""
    _state["path"], _state["data"] = None, None


if __name__ == "__main__":
    _say("存储: %s" % _store_path())
    _say(summary())
    _say(prompt_note())
