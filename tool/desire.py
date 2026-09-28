# -*- coding: utf-8 -*-
"""动机层：她"想做什么"（需求值 + 行为链）。

为什么要有
----------
以前的自主是**被动反应式**：屏幕变了就评价一句、时间到了就搭话 —— 都是"被触发"。
现在多一层**需求**，会随时间自己长：

    boredom   无聊度：独处越久越无聊 → 想找点事做
    social    想说话：越久没跟她说话越强 → 想跟你聊两句
    energy    精力：陪着你会慢慢消耗 → 太低了想歇会儿（话说短、不折腾）

再叠一个**活跃度**档位（config 的 `autonomy_level`）：

    quiet   安静：不主动开口、不主动动手（只回应主人）
    normal  适中（默认）
    active  活跃：更愿意开口、门槛更低

她"想做什么"会给模型一句动机说明（`note()`），由她自己决定怎么表达 —— 这才像"自己有想法"。
`tool.attention` 的安静/适中/活跃分档就取自这里的 `level()`。

存储：`pets/<角色>/memory/desire.json`；开关：无（完全本地、纯数值）
"""
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 需求增长速度（每小时）
BOREDOM_PER_HOUR = 14.0
SOCIAL_PER_HOUR = 18.0
ENERGY_PER_HOUR = 6.0
# 各类意图的冷却（秒）：别同一个念头反复出现
COOLDOWN = {"music": 2400, "talk": 1500, "look": 1800, "note": 4800, "rest": 7200,
            "play": 7200}
_LEVELS = ("quiet", "normal", "active")
_MAX_ELAPSED_H = 8.0          # 关机再久也别一次涨满


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "desire.json")


def _cfg_path() -> str:
    return os.path.join(os.getcwd(), "config.json")


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
        os.replace(tmp, p)              # 原子替换
    except Exception:
        pass


# ── 活跃度档位 ──────────────────────────────────────────────
def level() -> str:
    """自主活跃度档位（quiet / normal / active）—— tool.attention 也读它"""
    try:
        from tool.config import get_config
        v = str(get_config("./config.json").get("autonomy_level", "normal")).strip().lower()
        return v if v in _LEVELS else "normal"
    except Exception:
        return "normal"


def set_level(v: str) -> bool:
    """写活跃度档位。

    ⚠ 只改 `autonomy_level` 这一个键，**绝不**拿"示例配置"的内容去覆盖用户的 config.json：
      get_config() 在 config.json 缺失时会回落到 config.example.json，
      若照抄它整份写回去，等于把用户的配置换成示例（会丢他自己的设置）。
    """
    v = str(v).strip().lower()
    if v not in _LEVELS:
        return False
    try:
        p = _cfg_path()
        raw = {}
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    raw = json.load(f) or {}
            except Exception:
                raw = {}
        if not isinstance(raw, dict):
            raw = {}
        raw["autonomy_level"] = v
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _say("[动机] 自主活跃度 → %s" % v)
        return True
    except Exception as e:
        _say("[动机] ⚠ 写活跃度失败: %s" % e)
        return False


def next_level() -> str:
    cur = level()
    i = _LEVELS.index(cur)
    return _LEVELS[(i + 1) % len(_LEVELS)]


def level_label() -> str:
    return {"quiet": "安静", "normal": "适中", "active": "活跃"}.get(level(), "适中")


# ── 需求值 ──────────────────────────────────────────────────
def tick(talked: bool = False, screen_changed: bool = True, elapsed_sec: float = None) -> dict:
    """更新需求值：talked=刚说过话，screen_changed=主人在忙别的（屏幕有变化）"""
    d = _load()
    now = time.time()
    try:
        hours = max(0.0, float(elapsed_sec if elapsed_sec is not None
                               else (now - float(d.get("ts") or now))) / 3600.0)
        hours = min(hours, _MAX_ELAPSED_H)
        d["boredom"] = min(100.0, float(d.get("boredom") or 0) + BOREDOM_PER_HOUR * hours)
        d["social"] = min(100.0, float(d.get("social") or 0) + SOCIAL_PER_HOUR * hours)
        d["energy"] = max(0.0, float(d.get("energy") or 80) - ENERGY_PER_HOUR * hours)
        if talked:
            d["social"] = max(0.0, float(d["social"]) - 55.0)     # 聊过就解渴
            d["boredom"] = max(0.0, float(d["boredom"]) - 8.0)
        if screen_changed:
            d["boredom"] = max(0.0, float(d["boredom"]) - 12.0)   # 主人在忙别的 → 没那么无聊
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
    except Exception:
        pass
    _save(d)
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


def wants(music_playing: bool = None, user_idle_sec: float = None) -> dict:
    """她现在想做什么 → {} 或 {"kind":…, "text":…, "prompt":…}

    kind: talk（想跟你说说话） / note（想记点东西） / rest（有点累想歇会儿）
    """
    if level() == "quiet":
        return {}
    try:
        d = tick(elapsed_sec=0)          # 先按当前时钟结算一次
    except Exception:
        d = _load()
    b = float(d.get("boredom") or 0)
    s = float(d.get("social") or 0)
    e = float(d.get("energy") or 80)
    _b_th, _s_th = (55.0, 50.0) if level() == "active" else (70.0, 65.0)   # 活跃档门槛更低

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
    # ③ 想记点东西（安静的时候把最近的事理一理）
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
        return ("活跃度：%s｜无聊 %.0f｜想说话 %.0f｜精力 %.0f｜最近自己行动：%s"
                % (level_label(), float(d.get("boredom") or 0), float(d.get("social") or 0),
                   float(d.get("energy") or 0),
                   time.strftime("%m-%d %H:%M", time.localtime(float(last))) if last else "还没"))
    except Exception:
        return ""


if __name__ == "__main__":
    _say("存储: %s" % _path())
    _say(summary_text())
    _say("现在想做什么: %s" % (wants() or "（没什么特别想做的）"))
    _say("提示词: %s" % (note() or "（无）"))
