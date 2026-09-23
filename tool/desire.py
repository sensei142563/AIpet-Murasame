# -*- coding: utf-8 -*-
"""动机层：她"想做什么"（参考 OpenPets 的需求值 + Mitra 的行为链）。

以前的自主是被动反应式：屏幕变了就评价一句、时间到了就搭话 —— 都是"被触发"。
现在多一层**需求**，会随时间自己长：

    boredom   无聊度：独处越久、屏幕越久没变，越无聊 → 想找点事做（放首歌/找你说说话）
    social    想说话：越久没跟她说话越强 → 想跟你聊两句
    energy    精力：她"陪着你"会慢慢消耗 → 太低了会想歇一会儿（说话短、不想折腾）

再叠一个**活跃度**档位（config 的 autonomy_level）：

    quiet   安静：不主动开口、不主动动手（只回应主人，提醒照常）
    normal  适中（默认）：现在的节奏
    active  活跃：更愿意开口、间隔更短、更常自己找事做

她"想做什么"会给模型一句动机说明（例如"你现在有点无聊，想放首歌听"），
由她自己决定用【音乐】标记、去看屏幕、还是就找你说话 —— 这才像"自己有想法"。
存储：pets/<角色>/memory/desire.json
"""
import json
import os
import time

# 需求增长速度（每小时）
BOREDOM_PER_HOUR = 14.0
SOCIAL_PER_HOUR = 18.0
ENERGY_PER_HOUR = 6.0
# 各类意图的冷却（秒）：别同一个念头反复出现
COOLDOWN = {"music": 2400, "talk": 1500, "look": 1800, "note": 4800, "rest": 7200}

_LEVELS = ("quiet", "normal", "active")


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "desire.json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {"ts": time.time(), "boredom": 20.0, "social": 25.0, "energy": 80.0, "fired": {}}


def _save(d: dict):
    try:
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass


def level() -> str:
    """自主活跃度档位（quiet / normal / active）"""
    try:
        from tool.config import get_config
        v = str(get_config("./config.json").get("autonomy_level", "normal")).strip().lower()
        return v if v in _LEVELS else "normal"
    except Exception:
        return "normal"


def set_level(v: str) -> bool:
    v = str(v).strip().lower()
    if v not in _LEVELS:
        return False
    try:
        from tool.config import get_config
        cfg = dict(get_config("./config.json") or {})
        cfg["autonomy_level"] = v
        import os as _os
        p = _os.path.join("config.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _os.replace(tmp, p)
        print(f"[动机] 自主活跃度 → {v}")
        return True
    except Exception as e:
        print(f"[动机] ⚠ 写活跃度失败: {e}")
        return False


def next_level() -> str:
    cur = level()
    i = _LEVELS.index(cur)
    return _LEVELS[(i + 1) % len(_LEVELS)]


def level_label() -> str:
    return {"quiet": "安静", "normal": "适中", "active": "活跃"}.get(level(), "适中")


def tick(talked: bool = False, screen_changed: bool = True, elapsed_sec: float = None) -> dict:
    """更新需求值（无聊/想说话/精力）。talked=刚说过话，screen_changed=屏幕有变化"""
    d = _load()
    now = time.time()
    try:
        hours = max(0.0, float(elapsed_sec if elapsed_sec is not None else (now - float(d.get("ts") or now))) / 3600.0)
        hours = min(hours, 8.0)                 # 关机再久也别一次涨满
        d["boredom"] = min(100.0, float(d.get("boredom") or 0) + BOREDOM_PER_HOUR * hours)
        d["social"] = min(100.0, float(d.get("social") or 0) + SOCIAL_PER_HOUR * hours)
        d["energy"] = max(0.0, float(d.get("energy") or 80) - ENERGY_PER_HOUR * hours)
        if talked:
            d["social"] = max(0.0, float(d["social"]) - 55.0)   # 聊过就解渴
            d["boredom"] = max(0.0, float(d["boredom"]) - 8.0)
        if screen_changed:
            d["boredom"] = max(0.0, float(d["boredom"]) - 12.0)  # 主人在忙别的 → 没那么无聊
        # 心情好/关系近 → 更愿意找事做；心情差 → 想歇着
        try:
            from tool import state as _st
            m = _st.mood()
            if m > 75:
                d["boredom"] = min(100.0, float(d["boredom"]) + 4.0)
            elif m < 35:
                d["energy"] = max(0.0, float(d["energy"]) - 5.0)
        except Exception:
            pass
        d["ts"] = now
        _save(d)
    except Exception:
        pass
    return d


def _cool_ok(d: dict, kind: str) -> bool:
    try:
        last = float((d.get("fired") or {}).get(kind) or 0)
        return (time.time() - last) > float(COOLDOWN.get(kind, 1800))
    except Exception:
        return True


def _mark(d: dict, kind: str):
    try:
        fired = dict(d.get("fired") or {})
        fired[kind] = time.time()
        d["fired"] = fired
        _save(d)
    except Exception:
        pass


def wants(music_playing: bool = None) -> dict:
    """她现在想做什么 → {} 或 {"kind":…, "text":…, "prompt":…}

    kind: music（想放首歌） / talk（想跟你说说话） / look（想看看你在忙什么）
          / note（想记点东西） / rest（有点累想歇会儿）
    """
    lv = level()
    if lv == "quiet":
        return {}
    try:
        d = tick(elapsed_sec=0)     # 先按当前时钟结算一次
    except Exception:
        d = _load()
    b = float(d.get("boredom") or 0)
    s = float(d.get("social") or 0)
    e = float(d.get("energy") or 80)
    # 活跃档：更低的门槛
    _b_th, _s_th = (55.0, 50.0) if lv == "active" else (70.0, 65.0)

    # ① 太累了 → 想歇会儿（话说短、不折腾）
    if e < 25.0 and _cool_ok(d, "rest"):
        _mark(d, "rest")
        return {"kind": "rest", "text": "有点累了，想安静陪你待会儿",
                "prompt": "（你现在有点累。这一轮话说短一点、软一点，别折腾别主动做事，"
                          "就安静陪着他。）"}
    # ② 想说话
    if s >= _s_th and _cool_ok(d, "talk"):
        _mark(d, "talk")
        return {"kind": "talk", "text": "想找你聊两句",
                "prompt": "（你已经有一阵子没跟主人说话了，有点想他。主动找他说一句话，"
                          "自然一点，一两句就行，别硬找话题。）"}
    # ③ 无聊 → 想放首歌（如果他没在放的话）
    if b >= _b_th and music_playing is False and _cool_ok(d, "music"):
        _mark(d, "music")
        return {"kind": "music", "text": "有点无聊，想放首歌",
                "prompt": "（你现在有点无聊，想放首歌换换气氛。用【音乐】标记自己点一首，"
                          "你挑一首合适的（可以放他喜欢的、或者你喜欢的），"
                          "放完跟他说一句你为什么挑这首。）"}
    # ④ 想知道他在忙什么
    if b >= (_b_th - 10) and _cool_ok(d, "look"):
        _mark(d, "look")
        return {"kind": "look", "text": "想看看你在忙什么",
                "prompt": "（你想知道他这会儿在忙什么。输出一行「【看屏幕】」看一眼，"
                          "看清了再自然地说一句。）"}
    # ⑤ 想记点东西（把最近的事写进记忆）
    if _cool_ok(d, "note") and (b > 40 or s > 40):
        _mark(d, "note")
        return {"kind": "note", "text": "想把最近的事记一记",
                "prompt": "（安静的时候你想把最近的事理一理。不用说出来，"
                          "这轮只回一句很短的、带点心事的话就好。）"}
    return {}


def note() -> str:
    """给提示词的一句（让她知道自己现在什么状态）"""
    try:
        d = _load()
        b = float(d.get("boredom") or 0)
        s = float(d.get("social") or 0)
        e = float(d.get("energy") or 80)
        bits = []
        if b >= 70:
            bits.append("有点无聊，想找点事做")
        if s >= 65:
            bits.append("有点想主人了")
        if e <= 25:
            bits.append("精力不太够，想安静待着")
        if not bits:
            return ""
        return "【你现在的心情（自然流露，不要念出来）】" + "、".join(bits) + "。"
    except Exception:
        return ""


def summary_text() -> str:
    try:
        d = _load()
        fired = d.get("fired") or {}
        last = max(fired.values()) if fired else 0
        return ("活跃度：%s｜无聊 %.0f｜想说话 %.0f｜精力 %.0f｜最近自己行动：%s" % (
            level_label(), float(d.get("boredom") or 0), float(d.get("social") or 0),
            float(d.get("energy") or 0),
            time.strftime("%m-%d %H:%M", time.localtime(float(last))) if last else "还没"))
    except Exception:
        return ""


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("存储:", _path())
    print("活跃度:", level_label(), "（下一个：", level_label() if False else next_level(), "）")
    print("摘要:", summary_text())
    print()
    print("模拟：独处 3 小时（不聊天、屏幕没变）")
    for m in _load().get("fired", {}):
        pass
    d = _load()
    d["ts"] = time.time() - 3 * 3600
    d["fired"] = {}
    _save(d)
    print("  需求:", {k: round(float(v), 1) for k, v in tick(talked=False, screen_changed=False).items()
                    if k in ("boredom", "social", "energy")})
    w = wants(music_playing=False)
    print("  她想:", w.get("text") or "（没什么特别想的）")
    print("  动机提示:", (w.get("prompt") or "")[:70])
    print()
    print("  再问一次（冷却内）：", wants(music_playing=False).get("text") or "（冷却中，不重复 ✓）")
    print()
    print("聊天之后：", {k: round(float(v), 1) for k, v in tick(talked=True).items()
                     if k in ("boredom", "social", "energy")})
    print("注入提示:", note() or "（无）")
