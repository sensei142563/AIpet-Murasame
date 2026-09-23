# -*- coding: utf-8 -*-
"""提醒 / 待办 / 番茄钟：到点了她会主动叫你（参考 HealthMate / PetAI / OpenPets 那类做法）。

她能接的活（写一行标记就行）：
    【提醒】30分钟后 喝水          ← N 分钟/小时后提醒
    【提醒】20:30 开会             ← 今天某个时刻
    【提醒】明天 9:00 吃药         ← 明天某个时刻
    【提醒】每天 9:00 吃药         ← 每天重复
    【提醒】番茄钟 25              ← 25 分钟专注 + 休息提醒
    【提醒】有哪些                 ← 列出现在挂了哪些提醒
    【提醒】取消 喝水              ← 按关键词取消

到点之后：桌宠会用一个正常对话轮跟主人说（有语音、有立绘），并写日志。
存储：pets/<角色>/memory/reminders.json
"""
import json
import os
import re
import time

REMIND_MARK = "【提醒】"
_LINE = re.compile("[【\\[]\\s*提醒\\s*[】\\]]\\s*([^\"\\]\\n]{1,80})")
_MAX_ITEMS = 40
_last_fire = {"ts": 0.0, "key": ""}


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "reminders.json")


def _load() -> list:
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, list):
            return d
        if isinstance(d, dict) and isinstance(d.get("items"), list):
            return d["items"]
    except Exception:
        pass
    return []


def _save(items: list):
    try:
        items = sorted(items, key=lambda x: float(x.get("at") or 0))[-_MAX_ITEMS:]
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        print(f"[提醒] ⚠ 保存失败: {e}")


def _log(msg: str):
    try:
        print(f"[提醒] {msg}")
    except Exception:
        pass


def _now() -> float:
    return time.time()


def _fmt_ts(ts: float) -> str:
    try:
        t = time.localtime(float(ts))
        if time.strftime("%Y-%m-%d", t) == time.strftime("%Y-%m-%d"):
            return time.strftime("%H:%M", t)
        return time.strftime("%m-%d %H:%M", t)
    except Exception:
        return "?"


# ─────────────────────── 解析 ───────────────────────

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10, "半": 0.5}


def _num(s: str):
    try:
        m = re.search("(\\d+(?:\\.\\d+)?)", s)
        if m:
            return float(m.group(1))
        for ch, v in _CN_NUM.items():
            if ch in s:
                return float(v)
    except Exception:
        pass
    return None


def parse(text: str) -> list:
    """解析【提醒】标记 → [(动作, 参数)]"""
    out = []
    for m in _LINE.finditer(str(text or "")):
        s = re.sub("\\s+", " ", str(m.group(1) or "")).strip("：:，,。")
        if not s:
            continue
        if any(k in s for k in ("有哪些", "列表", "还有什么", "待办")):
            out.append(("list", ""))
            continue
        mm = re.match("^取消\\s*(.*)$", s)
        if mm:
            out.append(("cancel", mm.group(1).strip()))
            continue
        # 番茄钟
        if "番茄" in s:
            n = _num(s) or 25
            out.append(("pomodoro", int(max(5, min(180, n)))))
            continue
        # 每天 / 明天 / N 分钟后 / HH:MM
        daily = "每天" in s or "每日" in s
        tomorrow = "明天" in s
        when, what = None, ""
        m1 = re.match("^(?:每天|每日|明天)?\\s*(\\d+)\\s*(分钟|分|小时|时|秒)\\s*(?:后|之后)?\\s*(.*)$", s)
        m2 = re.match("^(?:每天|每日|明天)?\\s*(\\d{1,2})[:：](\\d{2})\\s*(.*)$", s)
        if m1:
            n = float(m1.group(1))
            unit = m1.group(2)
            secs = n * (3600 if unit in ("小时", "时") else (1 if unit == "秒" else 60))
            when, what = _now() + secs, m1.group(3)
        elif m2:
            hh, mi = int(m2.group(1)), int(m2.group(2))
            base = time.localtime(_now() + (86400 if tomorrow else 0))
            t = time.mktime((base.tm_year, base.tm_mon, base.tm_mday, hh, mi, 0, 0, 0, -1))
            if t <= _now():
                t += 86400                      # 今天这个点已经过了 → 顺延到明天（每天重复也一样）
            when, what = t, m2.group(3)
        if when is None:
            continue
        what = re.sub("^(提醒我|提醒|叫我|记得)", "", str(what or "")).strip("：:，,。\"'「」")
        if not what:
            what = "该做的事"
        out.append(("daily" if daily else "once", {"at": when, "what": what[:40]}))
    return out[:3]


def clean_for_speech(text: str) -> str:
    src = str(text or "")
    try:
        if not _LINE.search(src):
            return src
        return re.sub("\\n{2,}", chr(10), _LINE.sub("", src)).strip()
    except Exception:
        return src


# ─────────────────────── 增删查 ───────────────────────

def add(at: float, what: str, daily: bool = False) -> dict:
    items = _load()
    it = {"at": float(at), "what": str(what)[:40], "daily": bool(daily),
          "created": _now(), "done": False}
    items.append(it)
    _save(items)
    _log(f"记下提醒：{_fmt_ts(at)}（{'每天' if daily else '一次'}）{what}")
    return it


def add_after(seconds: float, what: str) -> dict:
    return add(_now() + max(5.0, float(seconds)), what)


def add_at_clock(hhmm: str, what: str, daily: bool = False, tomorrow: bool = False) -> dict:
    m = re.match("^(\\d{1,2})[:：](\\d{2})$", str(hhmm).strip())
    if not m:
        return {}
    hh, mi = int(m.group(1)), int(m.group(2))
    base = time.localtime(_now() + (86400 if tomorrow else 0))
    t = time.mktime((base.tm_year, base.tm_mon, base.tm_mday, hh, mi, 0, 0, 0, -1))
    if not daily and not tomorrow and t <= _now():
        t += 86400
    return add(t, what, daily)


def items() -> list:
    return [x for x in _load() if not x.get("done")]


def cancel(keyword: str) -> int:
    """按关键词取消（返回取消了几条）"""
    items = _load()
    k = str(keyword or "").strip()
    n = 0
    for it in items:
        if it.get("done"):
            continue
        if not k or k in str(it.get("what") or ""):
            it["done"] = True
            n += 1
    if n:
        _save(items)
        _log(f"取消 {n} 条提醒（关键词：{k or '全部'}）")
    return n


def list_text() -> str:
    its = items()
    if not its:
        return "现在没有挂着的提醒。"
    lines = ["现在挂着的提醒："]
    for it in its[:10]:
        lines.append("· %s%s %s" % ("每天 " if it.get("daily") else "",
                                    _fmt_ts(it.get("at")), str(it.get("what"))[:30]))
    return chr(10).join(lines)


def pomodoro(minutes: int = 25) -> str:
    """番茄钟：专注 + 休息"""
    add_after(minutes * 60, "番茄钟结束，起来休息一下")
    if minutes >= 15:
        add_after((minutes - 5) * 60, "快结束了（还剩 5 分钟）")
    return f"好，{minutes} 分钟番茄钟开始了，到点我叫你。"


# ─────────────────────── 到点检查 ───────────────────────

def due(now: float = None) -> list:
    """到点该提醒的（一次性的标记完成；每天的顺延到明天）"""
    now = float(now if now is not None else _now())
    items = _load()
    fired = []
    changed = False
    for it in items:
        if it.get("done"):
            continue
        try:
            at = float(it.get("at") or 0)
        except Exception:
            continue
        if at > now:
            continue
        fired.append(it)
        changed = True
        if it.get("daily"):
            # 顺延到明天同一时刻
            it["at"] = at + 86400
            while it["at"] <= now:
                it["at"] += 86400
        else:
            it["done"] = True
    if changed:
        _save(items)
    return fired


def take_due() -> list:
    """取一次到点的提醒（带去重：同一条 60 秒内不重复触发）"""
    out = []
    for it in due():
        k = "%s|%s" % (it.get("what"), int(float(it.get("at") or 0)))
        if _last_fire["key"] == k and _now() - float(_last_fire["ts"] or 0) < 60:
            continue
        _last_fire["key"], _last_fire["ts"] = k, _now()
        out.append(it)
    return out


def prompt_rules() -> str:
    return (
        "【提醒 / 待办（已开启）】你可以帮主人记事，到点桌宠会叫你开口提醒他。写一行：\n"
        "【提醒】30分钟后 喝水   ／   【提醒】20:30 开会   ／   【提醒】明天 9:00 吃药\n"
        "【提醒】每天 9:00 吃药   ／   【提醒】番茄钟 25   ／   【提醒】有哪些   ／   【提醒】取消 喝水\n"
        "★ 主人说「提醒我…」「X 点叫我…」「别忘了…」时就用它。\n"
        "★ 到点那一轮，桌宠会把提醒内容告诉你，你用自己的口吻说出来就好（别念标记）。"
    )


def summary_text() -> str:
    return list_text()


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=== 解析 ===")
    for t in ("【提醒】30分钟后 喝水", "【提醒】20:30 开会", "【提醒】明天 9:00 吃药",
              "【提醒】每天 9:00 吃药", "【提醒】番茄钟 25", "【提醒】有哪些", "【提醒】取消 喝水"):
        print("  %-26s → %s" % (t, parse(t)))
    print()
    print("=== 建两条 + 查 ===")
    add_after(1, "喝水")
    add_at_clock("23:59", "睡觉", daily=True)
    print(list_text())
    print()
    print("=== 到点检查（把第一条的时间改成 1 秒前）===")
    its = _load()
    for it in its:
        if it.get("what") == "喝水":
            it["at"] = _now() - 1
    _save(its)
    print("  到点：", [x.get("what") for x in take_due()])
    print("  再查一次（不该重复）：", [x.get("what") for x in take_due()])
    print()
    print("  取消 喝水 →", cancel("喝水"), "条")
    print(list_text())
