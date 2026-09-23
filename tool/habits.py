# -*- coding: utf-8 -*-
"""记录主人的习惯（自主学习的一部分）。

为什么要它（用户要求）："自主学习加个记录主人习惯的功能" ——
她自己学的是"知识"（自学到的内容、对主人的印象），但**生活习惯**得靠日常观察攒：
几点开始用电脑、什么时候还在熬夜、常开哪些软件、爱听什么、大概多久来一次。

记什么（都是**计数/时段**这类粗信息，不记你说过的话，不碰隐私内容）：
    * 每天第一次/最后一次互动的时间 → 起床、睡觉规律
    * 每个小时互动次数 → 活跃时段
    * 常用软件（窗口标题出现次数）→ 平时在用什么
    * 陪伴天数 / 互动总次数
存：pets/<角色>/memory/habits.json

给她用：prompt_note() 会把"他的习惯"塞进她的提示词，聊天时能自然提一句
       （"你这个点还在写东西啊，平时不是十一点就睡了"），而不是干巴巴背数据。
"""
import json
import os
import time

MAX_APPS = 40          # 最多记多少个"常用软件"
MAX_DAYS = 60          # 每天的时间戳最多留多少天


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
    d.setdefault("apps", {})        # 软件名 → 次数
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
            keep = sorted(apps.items(), key=lambda kv: -kv[1])[:MAX_APPS]
            d["apps"] = dict(keep)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"[习惯] ⚠ 保存失败: {type(e).__name__}: {e}")


def note_active(now: float = None):
    """记一次"主人来互动了"（每天第一次/最后一次、每小时分布）"""
    try:
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
    """记一次"看到这个窗口开着"（粗粒度：只记标题，用来统计常用软件）"""
    try:
        t = str(title or "").strip()
        if not t or len(t) > 40:
            return
        low = t.lower()
        if any(k in low for k in ("aipet", "桌宠", "program manager", "输入体验", "ime")):
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


def _avg(vals: list):
    return sum(vals) / float(len(vals)) if vals else None


def hours_text() -> str:
    """活跃时段（把一天分成几段，描述占比最高的几段）"""
    try:
        d = _load()
        hours = {int(k): int(v) for k, v in (d.get("hours") or {}).items()}
        if not hours:
            return ""
        total = sum(hours.values()) or 1
        # 早上 5-11 / 白天 11-18 / 晚上 18-24 / 深夜 0-5
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
        top = sorted(seg.items(), key=lambda kv: -kv[1])
        top = [(k, v) for k, v in top if v / float(total) >= 0.10]
        if not top:
            return ""
        return "、".join(f"{k}{int(v * 100 / total)}%" for k, v in top[:3])
    except Exception:
        return ""


def schedule_text() -> str:
    """作息：平均几点开始用电脑、几点还在用"""
    try:
        d = _load()
        days = list((d.get("days") or {}).values())
        if len(days) < 2:
            return ""
        firsts = [time.localtime(float(x["first"])).tm_hour + time.localtime(float(x["first"])).tm_min / 60.0
                  for x in days if x.get("first")]
        lasts = [time.localtime(float(x["last"])).tm_hour + time.localtime(float(x["last"])).tm_min / 60.0
                 for x in days if x.get("last")]
        out = []
        if firsts:
            a = _avg(firsts)
            out.append(f"一般 {int(a):02d}:{int((a % 1) * 60):02d} 前后开始找我")
        if lasts:
            b = _avg(lasts)
            hh, mm = int(b) % 24, int((b % 1) * 60)
            tip = "（常熬夜）" if b >= 23.5 or b < 5 else ""
            out.append(f"最晚到 {hh:02d}:{mm:02d} 还在用{tip}")
        return "，".join(out)
    except Exception:
        return ""


def apps_text(limit: int = 5) -> str:
    """常用软件（出现次数最多的几个）"""
    try:
        d = _load()
        apps = sorted((d.get("apps") or {}).items(), key=lambda kv: -kv[1])
        if not apps:
            return ""
        # 把次数太少的（只看过一两次的）滤掉，别把啥都写进去
        top = [(k, v) for k, v in apps if v >= 2][:limit] or apps[:2]
        return "、".join(f"{k}（{v} 次）" for k, v in top)
    except Exception:
        return ""


def music_text() -> str:
    """爱听的歌（复用她的听歌口味记录）"""
    try:
        from tool import music as _mu
        return _mu.favorites_text(4)
    except Exception:
        return ""


def summary_text() -> str:
    """给人看的一页（状态窗"习惯"页用）"""
    out = []
    sch = schedule_text()
    if sch:
        out.append("【作息】" + sch)
    hrs = hours_text()
    if hrs:
        out.append("【活跃时段】" + hrs)
    apps = apps_text()
    if apps:
        out.append("【常用软件】" + apps)
    mus = music_text()
    if mus:
        out.append("【爱听的歌】" + mus)
    try:
        d = _load()
        n = int(d.get("total") or 0)
        days = len(d.get("days") or {})
        if n:
            out.append(f"【互动】一共 {n} 次，记录了 {days} 天")
    except Exception:
        pass
    return chr(10).join(out) or "（还没观察到什么习惯——多陪我用几天就记下了）"


def prompt_note() -> str:
    """塞进她提示词里的"主人的习惯"（很短，一两句）"""
    try:
        d = _load()
        if int(d.get("total") or 0) < 5:
            return ""                      # 数据太少就别瞎猜
        bits = []
        sch = schedule_text()
        if sch:
            bits.append(sch)
        hrs = hours_text()
        if hrs:
            bits.append("他常在" + hrs.replace("、", "、") + "用电脑")
        apps = apps_text(3)
        if apps:
            bits.append("常开的是" + apps.split("（")[0] + "这些")
        if not bits:
            return ""
        return "（你平时观察到的他的习惯：" + "；".join(bits[:3])
    except Exception:
        return ""


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("存储:", _path())
    print("注一笔活跃 + 两个软件…")
    note_active()
    note_app("Microsoft Edge")
    note_app("DeepSeek 开放平台 - Microsoft Edge")
    print(summary_text())
    print()
    print("提示词里的一小段:", (prompt_note() or "（还不够）")[:120])
