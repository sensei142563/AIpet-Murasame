# -*- coding: utf-8 -*-
"""记录主人的习惯（自主学习的一部分）。

为什么要它
----------
她自己"学"的是**知识**（自学到的内容、对主人的印象），但**生活习惯**得靠日常观察攒：
几点开始用电脑、什么时候还在熬夜、常开哪些软件、大概多久来一次。

记什么（都是**计数/时段**这类粗信息，**不记你说过的话、不碰内容**）
--------------------------------------------------------------
    * 每天第一次/最后一次互动的时间 → 起床、睡觉规律
    * 每个小时互动次数                 → 活跃时段
    * 前台窗口标题出现次数（跳过本程序和输入法）→ 平时在用什么软件
    * 陪伴天数 / 互动总次数

存：`pets/<角色>/memory/habits.json`（本地文件，不走网络）
给她用：`prompt_note()` 把"他的习惯"塞进提示词，聊天时能自然带一句
       （"你这个点还在写东西啊，平时不是十一点就睡了"），而不是干巴巴背数据。

开关：config.json → `habits_enabled`（默认 true）；不想被记就改成 false。
上限：每天时间戳留 60 天、常用软件留 40 个（防止文件无限长）。
"""
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAX_APPS = 40          # 最多记多少个"常用软件"
MAX_DAYS = 60          # 每天的时间戳最多留多少天

# 这些标题不算"主人在用的软件"（本程序自己、输入法、系统壳）
_SKIP_TITLE = ("aipet", "桌宠", "program manager", "输入体验", "ime", "windows 默认锁屏")


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def enabled() -> bool:
    """开关（默认开；不想被记就设 habits_enabled=false）"""
    try:
        from tool.config import get_config, as_bool
        return as_bool(get_config("./config.json").get("habits_enabled", "true"), True)
    except Exception:
        return True


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "habits.json")


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f) or {}
    except Exception:
        d = {}
    d.setdefault("days", {})        # "2026-09-24" → {"first": ts, "last": ts, "n": 次数}
    d.setdefault("hours", {})       # "0"~"23" → 次数
    d.setdefault("apps", {})        # 软件/窗口标题 → 次数
    d.setdefault("total", 0)        # 总互动次数
    return d


def _save(d: dict):
    try:
        days = d.get("days") or {}
        if len(days) > MAX_DAYS:
            for k in sorted(days)[:-MAX_DAYS]:
                days.pop(k, None)
        apps = d.get("apps") or {}
        if len(apps) > MAX_APPS:
            d["apps"] = dict(sorted(apps.items(), key=lambda kv: -kv[1])[:MAX_APPS])
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception as e:
        _say("[习惯] ⚠ 保存失败: %s: %s" % (type(e).__name__, e))


def note_active(now: float = None):
    """记一次"主人来互动了"（每天第一次/最后一次 + 每小时分布 + 总数）"""
    try:
        if not enabled():
            return
        now = float(now or time.time())
        d = _load()
        day = _today()
        e = d["days"].get(day) or {}
        if not e.get("first"):
            e["first"] = now
        e["last"] = now
        e["n"] = int(e.get("n") or 0) + 1
        d["days"][day] = e
        h = str(time.localtime(now).tm_hour)
        d["hours"][h] = int(d["hours"].get(h) or 0) + 1
        d["total"] = int(d.get("total") or 0) + 1
        _save(d)
    except Exception:
        pass


def note_app(title: str):
    """记一次"看到这个窗口开着"（只记标题用来统计常用软件，跳过本程序/输入法）"""
    try:
        if not enabled():
            return
        t = str(title or "").strip()
        if not t or len(t) > 40:
            return
        low = t.lower()
        if any(k in low for k in _SKIP_TITLE):
            return
        d = _load()
        d["apps"][t] = int(d["apps"].get(t) or 0) + 1
        _save(d)
    except Exception:
        pass


def note_apps_block(text: str):
    """从"现在开着的窗口：A；B；C"这类文本里批量记一笔"""
    try:
        for part in str(text or "").replace("现在开着的窗口：", "").split("；"):
            p = part.strip()
            if p:
                note_app(p)
    except Exception:
        pass


def foreground_title() -> str:
    """当前前台窗口标题（拿不到返回空串）。

    ⚠ 我们自己实现，是为了不依赖"列出所有窗口"那类模块 ——
      习惯统计只需要**前台**这一个标题，越少碰系统越好。
    """
    try:
        import ctypes
        u = ctypes.windll.user32
        h = u.GetForegroundWindow()
        if not h:
            return ""
        n = int(u.GetWindowTextLengthW(h))
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(h, buf, n + 1)
        return (buf.value or "").strip()
    except Exception:
        return ""


def poll_foreground() -> str:
    """采一次前台窗口并记账（定时器里调；返回标题便于排查）"""
    t = foreground_title()
    if t:
        note_app(t)
    return t


def _avg(vals: list):
    return sum(vals) / float(len(vals)) if vals else None


def hours_text() -> str:
    """活跃时段（把一天分段，描述占比最高的几段）"""
    try:
        hours = {int(k): int(v) for k, v in (_load().get("hours") or {}).items()}
        if not hours:
            return ""
        total = sum(hours.values()) or 1
        seg = {"早上": 0, "白天": 0, "晚上": 0, "深夜": 0}
        for h, n in hours.items():
            if 5 <= h < 11:
                seg["早上"] += n
            elif 11 <= h < 18:
                seg["白天"] += n
            elif 18 <= h < 24:
                seg["晚上"] += n
            else:
                seg["深夜"] += n
        top = [(k, v) for k, v in sorted(seg.items(), key=lambda kv: -kv[1])
               if v / float(total) >= 0.10]
        if not top:
            return ""
        return "、".join("%s%d%%" % (k, int(v * 100 / total)) for k, v in top[:3])
    except Exception:
        return ""


def schedule_text() -> str:
    """作息：平均几点开始用电脑、几点还在用（≥2 天才给，避免第一天就下结论）"""
    try:
        days = list((_load().get("days") or {}).values())
        if len(days) < 2:
            return ""
        def _hm(ts):
            lt = time.localtime(float(ts))
            return lt.tm_hour + lt.tm_min / 60.0
        firsts = [_hm(x["first"]) for x in days if x.get("first")]
        lasts = [_hm(x["last"]) for x in days if x.get("last")]
        out = []
        if firsts:
            a = _avg(firsts)
            out.append("一般 %02d:%02d 前后开始找我" % (int(a), int((a % 1) * 60)))
        if lasts:
            b = _avg(lasts)
            tip = "（常熬夜）" if (b >= 23.5 or b < 5) else ""
            out.append("最晚到 %02d:%02d 还在用%s" % (int(b) % 24, int((b % 1) * 60), tip))
        return "，".join(out)
    except Exception:
        return ""


def apps_text(limit: int = 5) -> str:
    """常用软件（次数最多的几个；只看过一两次的不写进来）"""
    try:
        apps = sorted((_load().get("apps") or {}).items(), key=lambda kv: -kv[1])
        if not apps:
            return ""
        top = [(k, v) for k, v in apps if v >= 2][:limit] or apps[:2]
        return "、".join("%s（%d 次）" % (k, v) for k, v in top)
    except Exception:
        return ""


def music_text() -> str:
    """爱听的歌（本仓库还没有"听歌口味"来源 → 返回空；将来有源就在这里接）"""
    return ""


def summary_text() -> str:
    """给人看的一页（状态窗的"习惯"页用）"""
    out = []
    for label, fn in (("【作息】", schedule_text), ("【活跃时段】", hours_text),
                      ("【常用软件】", apps_text), ("【爱听的歌】", music_text)):
        try:
            v = fn()
        except Exception:
            v = ""
        if v:
            out.append(label + v)
    try:
        d = _load()
        n, days = int(d.get("total") or 0), len(d.get("days") or {})
        if n:
            out.append("【互动】一共 %d 次，记录了 %d 天" % (n, days))
    except Exception:
        pass
    return "\n".join(out)


def prompt_note() -> str:
    """给模型的一句话（自然带出习惯，别背数据）"""
    try:
        bits = []
        sch = schedule_text()
        if sch:
            bits.append(sch)
        hrs = hours_text()
        if hrs:
            bits.append("常活跃时段：" + hrs)
        apps = apps_text(3)
        if apps:
            bits.append("最近常用：" + apps)
        if not bits:
            return ""
        return "【主人的习惯（你观察到的，自然带一句就好，不要背数据）】" + "；".join(bits) + "。"
    except Exception:
        return ""


if __name__ == "__main__":
    _say("开关: %s" % enabled())
    _say("存储: %s" % _path())
    _say("前台窗口: %r" % foreground_title())
    _say(summary_text() or "（还没攒到数据）")
    _say(prompt_note())
