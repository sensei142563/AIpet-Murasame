# -*- coding: utf-8 -*-
"""提醒 / 待办 / 番茄钟：到点了她会主动叫你。

她能接的活（模型写一行标记就行，语法由 `prompt_rules()` 注入提示词）：

    【提醒】30分钟后 喝水          ← N 分钟/小时后提醒
    【提醒】20:30 开会             ← 今天某个时刻（已过则顺延到明天）
    【提醒】明天 9:00 吃药         ← 明天某个时刻
    【提醒】每天 9:00 吃药         ← 每天重复
    【提醒】番茄钟 25              ← 25 分钟专注 + 提前 5 分钟提醒 + 结束休息
    【提醒】有哪些                 ← 列出现在挂着的提醒
    【提醒】取消 喝水              ← 按关键词取消

到点之后：桌宠用一个正常对话轮跟主人说（有语音、有立绘），并写日志。
**与"主动关怀"的区别**：提醒是主人自己要求的事，所以**到点一定会说**（只让勿扰模式挡），
不参与"开口时机"那套打分 —— 打分只用来决定她自己想聊的时候要不要开口。

存储：`pets/<角色>/memory/reminders.json`（最多留 40 条，原子替换）
开关：`reminder_enabled`（默认 true）
"""
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REMIND_MARK = "【提醒】"
_LINE = re.compile(r"[【\[]\s*提醒\s*[】\]]\s*([^\"\]\n]{1,80})")
MAX_ITEMS = 40
_last_fire = {"ts": 0.0, "key": ""}

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10, "半": 0.5}


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def enabled() -> bool:
    try:
        from tool.config import get_config, as_bool
        return as_bool(get_config("./config.json").get("reminder_enabled", "true"), True)
    except Exception:
        return True


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
        items = sorted(items, key=lambda x: float(x.get("at") or 0))[-MAX_ITEMS:]
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        _say("[提醒] ⚠ 保存失败: %s" % e)


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


def _num(s: str):
    try:
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if m:
            return float(m.group(1))
        for ch, v in _CN_NUM.items():
            if ch in s:
                return float(v)
    except Exception:
        pass
    return None


# ─────────────────────── 解析 ───────────────────────
def parse(text: str) -> list:
    """解析【提醒】标记 → [(动作, 参数)]"""
    out = []
    for m in _LINE.finditer(str(text or "")):
        s = re.sub(r"\s+", " ", str(m.group(1) or "")).strip("：:，,。")
        if not s:
            continue
        if any(k in s for k in ("有哪些", "列表", "还有什么", "待办")):
            out.append(("list", ""))
            continue
        mm = re.match(r"^取消\s*(.*)$", s)
        if mm:
            out.append(("cancel", mm.group(1).strip()))
            continue
        if "番茄" in s:
            n = _num(s) or 25
            out.append(("pomodoro", int(max(5, min(180, n)))))
            continue
        daily = ("每天" in s) or ("每日" in s)
        tomorrow = "明天" in s
        when, what = None, ""
        m1 = re.match(r"^(?:每天|每日|明天)?\s*(\d+)\s*(分钟|分|小时|时|秒)\s*(?:后|之后)?\s*(.*)$", s)
        m2 = re.match(r"^(?:每天|每日|明天)?\s*(\d{1,2})[:：](\d{2})\s*(.*)$", s)
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
                t += 86400                  # 今天这个点已经过了 → 顺延到明天
            when, what = t, m2.group(3)
        if when is None:
            continue
        what = re.sub(r"^(提醒我|提醒|叫我|记得)", "", str(what or "")).strip("：:，,。\"'「」")
        if not what:
            what = "该做的事"
        out.append(("daily" if daily else "once", {"at": when, "what": what[:40]}))
    return out[:3]


def clean_for_speech(text: str) -> str:
    """把标记从要说出口的句子里去掉（主人不该听到【提醒】这种东西）"""
    src = str(text or "")
    try:
        if not _LINE.search(src):
            return src
        return re.sub(r"\n{2,}", "\n", _LINE.sub("", src)).strip()
    except Exception:
        return src


# ─────────────────────── 增删查 ───────────────────────
def add(at: float, what: str, daily: bool = False) -> dict:
    items = _load()
    it = {"at": float(at), "what": str(what)[:40], "daily": bool(daily),
          "created": _now(), "done": False}
    items.append(it)
    _save(items)
    _say("[提醒] 记下：%s（%s）%s" % (_fmt_ts(at), "每天" if daily else "一次", what))
    return it


def add_after(seconds: float, what: str) -> dict:
    return add(_now() + max(5.0, float(seconds)), what)


def add_at_clock(hhmm: str, what: str, daily: bool = False, tomorrow: bool = False) -> dict:
    m = re.match(r"^(\d{1,2})[:：](\d{2})$", str(hhmm).strip())
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
    its = _load()
    k = str(keyword or "").strip()
    n = 0
    for it in its:
        if it.get("done"):
            continue
        if not k or k in str(it.get("what") or ""):
            it["done"] = True
            n += 1
    if n:
        _save(its)
        _say("[提醒] 取消 %d 条（关键词：%s）" % (n, k or "全部"))
    return n


def list_text() -> str:
    its = items()
    if not its:
        return "现在没有挂着的提醒。"
    lines = ["现在挂着的提醒："]
    for it in its[:10]:
        lines.append("· %s%s %s" % ("每天 " if it.get("daily") else "",
                                    _fmt_ts(it.get("at")), str(it.get("what"))[:30]))
    return "\n".join(lines)


def pomodoro(minutes: int = 25) -> str:
    """番茄钟：专注 + 提前 5 分钟提个醒 + 结束休息"""
    add_after(minutes * 60, "番茄钟结束，起来休息一下")
    if minutes >= 15:
        add_after((minutes - 5) * 60, "快结束了（还剩 5 分钟）")
    return "好，%d 分钟番茄钟开始了，到点我叫你。" % minutes


# ─────────────────────── 到点检查 ───────────────────────
def due(now: float = None) -> list:
    """到点该提醒的（一次性的标记完成；每天的顺延到明天）"""
    now = float(now if now is not None else _now())
    its = _load()
    fired = []
    changed = False
    for it in its:
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
            it["at"] = at + 86400
            while it["at"] <= now:
                it["at"] += 86400
        else:
            it["done"] = True
    if changed:
        _save(its)
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


def fire_prompt(it: dict) -> str:
    """到点那一轮给模型的话（用她自己的口吻说出来，别念标记）"""
    return ("（系统提示：你之前答应提醒主人的事到点了，内容：「%s」。"
            "用你自己的口吻自然地说出来，一句话就好，别提系统提示、别念标记。）"
            % str((it or {}).get("what") or "")[:60])


# ─────────────────────── 回复处理 / 提示词 ───────────────────────
def handle_reply(reply: str) -> str:
    """把模型回复里的【提醒】标记执行掉，并返回可以照常显示的文本。

    · once / daily / pomodoro → 记下；模型自己的话已经足够，这里不再补话
    · list   → 把「现在挂着的提醒」附在后面（否则主人看不到列表）
    · cancel → 附一句取消了几条
    """
    src = str(reply or "")
    if REMIND_MARK not in src and "[提醒]" not in src:
        return src
    todo = parse(src)
    cleaned = clean_for_speech(src)
    extra = []
    try:
        if not enabled():
            return cleaned
        for act, arg in todo:
            if act in ("once", "daily"):
                add(arg["at"], arg["what"], daily=(act == "daily"))
            elif act == "pomodoro":
                extra.append(pomodoro(int(arg)))
            elif act == "list":
                extra.append(list_text())
            elif act == "cancel":
                n = cancel(arg)
                extra.append("（取消 %d 条）" % n if n else "（没找到要取消的提醒）")
    except Exception as e:
        _say("[提醒] ⚠ 处理失败: %s" % e)
    if extra:
        return (cleaned + "\n" + "\n".join(extra)).strip()
    return cleaned


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
    _say("=== 解析 ===")
    for t in ("【提醒】30分钟后 喝水", "【提醒】20:30 开会", "【提醒】明天 9:00 吃药",
              "【提醒】每天 9:00 吃药", "【提醒】番茄钟 25", "【提醒】有哪些", "【提醒】取消 喝水"):
        _say("  %-26s → %s" % (t, parse(t)))
    _say("")
    _say("=== 记两条 + 查 ===")
    add_after(3600, "喝水")
    add_at_clock("23:59", "睡觉", daily=True)
    _say(list_text())
    _say("")
    _say("=== 回复处理 ===")
    _say(handle_reply("好呀，我记下了【提醒】30分钟后 喝水"))
    _say(summary_text())
