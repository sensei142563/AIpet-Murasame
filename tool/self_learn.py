# -*- coding: utf-8 -*-
"""自主学习：让她自己记住东西、自己学点东西、自己写日记。

开关：右键菜单 →「📖 自主学习」→ config.json 的 `learn_enabled`（**默认关**，会花模型调用）
存储：`pets/<角色>/memory/learned.json`（随时可以打开看）

三件事
------
1. **归纳记忆**：聊完一段，她自己提炼"关于主人的事"（喜好、习惯、正在忙什么）与"我自己的心情"，
   存成长期记忆；以后聊天会带上（不用每次重问）。
2. **自习**：主人不在的时候，她挑一个话题让模型给她讲一小段，存成"我学到的东西"。
3. **日记**：每天写一段，记今天聊了什么、心情如何。

记忆分四层（参考 AgentPet / Miru 那类做法）
    working   正在做的事（最近一次任务与结果）
    episodic  情节记忆：发生过的具体事件（带时间，留最近 200 条 / 30 天）
    semantic  语义记忆：从经历里提炼出来的事实与偏好（notes）
    profile   关于主人的画像（键值式，稳定不易变）
    sensory   感官（当前屏幕/会话的即时信息）**不落盘**，会过期，放在对话历史里

省钱 / 防打扰（照对方那套的保险丝，一个不少）
    · 一次只做一件事，间隔默认 20 分钟；主人最近 3 分钟说过话就不做（不抢对话）
    · 每次只调用一次小请求（≤400 token），一天最多 40 次
    · 只写日志、绝不打断桌宠（调用方丢进后台线程）
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

MAX_NOTES = 400                 # 长期记忆上限（超过优先丢最旧的"知识类"）
MAX_EPISODES = 200              # 情节记忆条数上限
EPISODE_DAYS = 30               # 情节记忆保留天数
CYCLE_GAP_MIN = 20              # 两次自主学习的最小间隔（分钟）
IDLE_NEED_SEC = 180             # 主人多久没说话才算"空闲"
DIARY_HOUR = 21                 # 这个点之后写今天的日记
DAILY_CALL_CAP = 40             # 一天的模型调用上限（保险丝）

_last_cycle = [0.0]
_last_call_day = ["", 0]        # (日期, 次数)


def _say(msg: str) -> None:
    try:
        print("[学习] %s" % msg)
    except Exception:
        pass
    try:
        p = os.path.join("data", "self_learn.log")
        os.makedirs("data", exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _cfg_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "config.json")


def _cfg(key, default=None):
    try:
        from tool.config import get_config
        return get_config("./config.json").get(key, default)
    except Exception:
        return default


def enabled() -> bool:
    try:
        from tool.config import as_bool
        return as_bool(_cfg("learn_enabled", "false"), False)
    except Exception:
        return str(_cfg("learn_enabled", "false")).strip().lower() in ("true", "1", "yes", "on")


def set_enabled(on: bool) -> bool:
    """写开关（只改这一个键，**不拿示例配置覆盖**用户的 config.json）"""
    try:
        p = _cfg_path()
        cfg = {}
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    cfg = json.load(f) or {}
            except Exception:
                cfg = {}
        if not isinstance(cfg, dict):
            cfg = {}
        cfg["learn_enabled"] = "true" if on else "false"
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _say("自主学习 → %s" % ("已开启" if on else "已关闭"))
        return True
    except Exception as e:
        _say("开关写入失败: %s" % e)
        return False


# ─────────────────────── 存储 ───────────────────────
def _store_path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "learned.json")


def _load() -> dict:
    base = {"notes": [], "diary": {}, "topic_ideas": [], "episodes": [],
            "working": {}, "profile": {}}
    try:
        with open(_store_path(), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            base.update(d)
            for k, t in (("notes", list), ("episodes", list), ("topic_ideas", list),
                         ("working", dict), ("profile", dict), ("diary", dict)):
                if not isinstance(base.get(k), t):
                    base[k] = t()
    except Exception:
        pass
    return base


def _save(d: dict):
    try:
        notes = d.get("notes") or []
        if len(notes) > MAX_NOTES:
            # 先丢最旧的"知识类"；关于主人的事实（fact）优先留着
            keep = [n for n in notes if n.get("kind") != "knowledge"]
            drop = sorted([n for n in notes if n.get("kind") == "knowledge"],
                          key=lambda n: float(n.get("ts") or 0))
            need = MAX_NOTES - len(keep)
            d["notes"] = sorted(keep + drop[-max(0, need):],
                                key=lambda n: float(n.get("ts") or 0))
        p = _store_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        _say("记忆写入失败: %s" % e)


def add_note(kind: str, text: str, topic: str = "") -> bool:
    text = str(text or "").strip()
    if not text:
        return False
    d = _load()
    d.setdefault("notes", []).append({"ts": time.time(), "kind": str(kind or "note"),
                                      "topic": str(topic)[:40], "text": text[:600]})
    _save(d)
    _say("记下一条（%s）：%s" % (kind, text[:60]))
    return True


def notes(kind: str = "") -> list:
    try:
        ns = list(_load().get("notes") or [])
        if kind:
            ns = [n for n in ns if n.get("kind") == kind]
        return ns
    except Exception:
        return []


def add_episode(text: str, kind: str = "event") -> bool:
    """记一条情节记忆（发生过的事：任务、成败、互动），留最近 200 条 / 30 天"""
    text = str(text or "").strip()
    if not text:
        return False
    try:
        d = _load()
        eps = list(d.get("episodes") or [])
        eps.append({"ts": time.time(), "kind": kind, "text": text[:200]})
        cut = time.time() - EPISODE_DAYS * 86400
        eps = [e for e in eps if float(e.get("ts") or 0) >= cut][-MAX_EPISODES:]
        d["episodes"] = eps
        _save(d)
        return True
    except Exception as e:
        _say("记情节失败: %s" % e)
        return False


def episodes(n: int = 5) -> list:
    try:
        eps = sorted(_load().get("episodes") or [], key=lambda x: float(x.get("ts") or 0))
        return eps[-max(1, int(n)):]
    except Exception:
        return []


def set_working(task: str, ok: bool = True, note: str = ""):
    """记"刚才在做什么、成没成"（工作记忆层）"""
    try:
        d = _load()
        d["working"] = {"ts": time.time(), "task": str(task)[:120], "ok": bool(ok),
                        "note": str(note)[:120]}
        _save(d)
    except Exception:
        pass


def working() -> dict:
    try:
        return dict(_load().get("working") or {})
    except Exception:
        return {}


def set_profile(key: str, value: str):
    """记一条关于主人的画像（语义层，键值式）"""
    try:
        d = _load()
        prof = dict(d.get("profile") or {})
        prof[str(key)[:16]] = str(value)[:60]
        d["profile"] = prof
        _save(d)
    except Exception:
        pass


def profile_text() -> str:
    try:
        prof = _load().get("profile") or {}
        if not prof:
            return ""
        return "、".join("%s：%s" % (k, v) for k, v in list(prof.items())[:8])
    except Exception:
        return ""


def diary_of(day: str = "") -> str:
    try:
        day = day or time.strftime("%Y-%m-%d")
        return str((_load().get("diary") or {}).get(day) or "")
    except Exception:
        return ""


def _set_diary(day: str, text: str):
    try:
        d = _load()
        diary = dict(d.get("diary") or {})
        diary[str(day)] = str(text)[:1500]
        # 只留最近 120 天
        if len(diary) > 120:
            for k in sorted(diary)[:-120]:
                diary.pop(k, None)
        d["diary"] = diary
        _save(d)
    except Exception:
        pass


def summary_text(limit: int = 10) -> str:
    """给人看的一页（右键"看看她学了什么"）"""
    d = _load()
    out = []
    prof = profile_text()
    if prof:
        out.append("【她对你的印象】" + prof)
    ns = sorted(d.get("notes") or [], key=lambda n: -float(n.get("ts") or 0))[:limit]
    if ns:
        out.append("【记下的事】")
        for n in ns:
            out.append("· [%s] %s" % (n.get("kind") or "", str(n.get("text"))[:80]))
    eps = episodes(5)
    if eps:
        out.append("【最近发生的】")
        for e in eps:
            try:
                ts = time.strftime("%m-%d %H:%M", time.localtime(float(e.get("ts") or 0)))
            except Exception:
                ts = ""
            out.append("· %s %s" % (ts, str(e.get("text"))[:80]))
    today = diary_of()
    if today:
        out.append("【今天的日记】" + today[:300])
    return "\n".join(out) if out else "（她还没学什么东西）"


# ─────────────────────── 召回 ───────────────────────
def _keywords(text: str, n: int = 6) -> list:
    out = []
    try:
        for m in re.finditer(r"[A-Za-z]{2,}", str(text or "")):
            out.append(m.group(0).lower())
        zh = re.sub(r"[^\u4e00-\u9fff]", "", str(text or ""))
        for i in range(len(zh) - 1):
            out.append(zh[i:i + 2])
    except Exception:
        pass
    # 去重保序
    seen, uniq = set(), []
    for w in out:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq[:n]


def memory_note(user_text: str = "", limit: int = 6) -> str:
    """拼一段"你记住的事"交给模型（按相关度挑，分层给）

    语义（稳定事实/画像）→ 情节（最近发生的）→ 工作（刚才在做什么）→ 日记。
    和主人这句话相关的排前面（关键词命中加权 + 新的略优先）。
    """
    try:
        if not enabled():
            return ""
        u = str(user_text or "")
        picked = []
        for n in notes():
            t = str(n.get("text") or "").strip()
            if not t:
                continue
            try:
                sc = float(n.get("ts") or 0) / 1e9
            except Exception:
                sc = 0.0
            if u:
                for w in _keywords(t):
                    if w and w in u:
                        sc += 1.5
            if n.get("kind") == "fact":
                sc += 0.4
            picked.append((sc, t))
        picked.sort(key=lambda x: -x[0])
        lines = [t for _s, t in picked[:max(1, int(limit))]]
        ep_lines = []
        for e in episodes(3):
            try:
                ts = time.strftime("%m-%d %H:%M", time.localtime(float(e.get("ts") or 0)))
            except Exception:
                ts = ""
            ep_lines.append("· %s %s" % (ts, str(e.get("text"))[:120]))
        w = working()
        w_line = ""
        try:
            if w and (time.time() - float(w.get("ts") or 0)) < 6 * 3600:
                w_line = ("· 刚才在忙：" + str(w.get("task"))[:80]
                          + ("（做成了）" if w.get("ok") else "（没做成）"))
        except Exception:
            pass
        if not (lines or ep_lines or w_line):
            return ""
        out = []
        if lines:
            out.append("【你记住的事（长期记忆，自然使用，不要念出来）】")
            out.extend("· " + t[:160] for t in lines)
        prof = profile_text()
        if prof:
            out.append("【你对主人的印象】" + prof)
        if ep_lines:
            out.append("【最近发生的】")
            out.extend(ep_lines)
        if w_line:
            out.append(w_line)
        today = diary_of()
        if today:
            out.append("【你今天的日记（自己看过就行）】" + today[:300])
        return "\n".join(out)
    except Exception:
        return ""


def _recent_history_text(history: list, n: int = 8) -> str:
    out = []
    try:
        for m in list(history or [])[-int(n):]:
            if isinstance(m, dict):
                out.append("%s：%s" % (m.get("role") or "?", str(m.get("content"))[:200]))
            elif isinstance(m, (list, tuple)) and len(m) >= 2:
                out.append("%s：%s" % (m[0], str(m[1])[:200]))
    except Exception:
        pass
    return "\n".join(out)[-3000:]


# ─────────────────────── 模型调用（带保险丝） ───────────────────────
def _budget_ok() -> bool:
    day = time.strftime("%Y-%m-%d")
    if _last_call_day[0] != day:
        _last_call_day[0], _last_call_day[1] = day, 0
    return _last_call_day[1] < DAILY_CALL_CAP


def _ask(system: str, user: str, max_tokens: int = 400) -> str:
    """问她当前用的那个模型（云端优先，本地也能用）。失败返回空串。"""
    if not _budget_ok():
        return ""
    model_type = str(_cfg("model_type", "deepseek") or "deepseek")
    try:
        if model_type == "local":
            from tool.chat import ollama_post
            r = ollama_post("qwen3:14b", {"model": "qwen3:14b",
                                          "prompt": system + "\n\n" + user,
                                          "stream": False,
                                          "options": {"num_predict": max_tokens}})
            try:
                txt = str((r or {}).get("message", {}).get("content") or r.get("response") or "")
            except Exception:
                txt = ""
        else:
            from tool.cloud_API_chat import post
            from longtext.model_config import get_short_model_config
            cfg = get_short_model_config()
            if not cfg:
                return ""
            payload = {"messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}],
                       "model": cfg["model"], "max_tokens": max_tokens, "stream": False}
            payload.update(cfg.get("reasoning") or {})
            txt = post("自学", payload, api_key=cfg["api_key"])
        _last_call_day[1] += 1
        return str(txt or "").strip()
    except Exception as e:
        _say("调用失败: %s: %s" % (type(e).__name__, e))
        return ""


def _json_obj(text: str) -> dict:
    try:
        m = re.search(r"\{.*\}", str(text or ""), re.S)
        obj = json.loads(m.group(0)) if m else {}
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _json_list(text: str) -> list:
    try:
        m = re.search(r"\[.*\]", str(text or ""), re.S)
        arr = json.loads(m.group(0)) if m else []
        return [str(x).strip() for x in arr if str(x).strip()] if isinstance(arr, list) else []
    except Exception:
        return []


# ─────────────────────── 三件事 ───────────────────────
def reflect(history: list, pet_name: str = "我") -> int:
    """归纳记忆：从最近对话里提炼"关于主人的事/我的心情"，返回记下几条"""
    convo = _recent_history_text(history, 10)
    if not convo.strip():
        return 0
    out = _ask(
        "你是%s。下面是你和主人的一段聊天记录。请提炼 2~4 条**值得长期记住**的事，"
        "用 JSON 数组输出，每条是 {\"kind\": \"fact|prefer|mood\", \"text\": \"…\"}。"
        "fact=关于主人的事实/习惯，prefer=主人的喜好，mood=你自己的心情。"
        "只输出 JSON，别写别的。" % pet_name, convo, max_tokens=400)
    items = []
    try:
        m = re.search(r"\[.*\]", str(out), re.S)
        arr = json.loads(m.group(0)) if m else []
        for x in (arr if isinstance(arr, list) else [])[:6]:
            if isinstance(x, dict) and str(x.get("text") or "").strip():
                items.append((str(x.get("kind") or "fact")[:12], str(x["text"]).strip()))
            elif isinstance(x, str) and x.strip():
                items.append(("fact", x.strip()))
    except Exception as e:
        _say("归纳结果解析失败: %s" % e)
    n = 0
    for kind, text in items:
        if add_note(kind, text):
            n += 1
    if n:
        _say("归纳了 %d 条记忆" % n)
    return n


def study(history: list, pet_name: str = "我") -> str:
    """自习：挑一个话题让模型讲一小段，存成"我学到的东西"（返回学到的那段）"""
    d = _load()
    ideas = [str(x) for x in (d.get("topic_ideas") or []) if str(x).strip()]
    convo = _recent_history_text(history, 6)
    topic = ideas[0] if ideas else ""
    if not topic:
        picked = _ask(
            "你是%s。看下面这段和主人的聊天，挑**一个**你还没搞懂、或者主人提过的话题，"
            "只回一个短句（不超过 12 个字），不要解释。" % pet_name, convo or "（最近没怎么聊）",
            max_tokens=60)
        topic = (picked or "").strip().splitlines()[0][:40] if picked else ""
    if not topic:
        return ""
    learned = _ask(
        "你是%s。请用 3~5 句、口语化的方式给**你自己**讲清楚「%s」，"
        "像写给自己看的小笔记，别用列表、别客套。" % (pet_name, topic), "讲讲看",
        max_tokens=400)
    if not learned:
        return ""
    add_note("knowledge", "%s：%s" % (topic, learned), topic=topic)
    if ideas and topic == ideas[0]:
        ideas = ideas[1:]
        d["topic_ideas"] = ideas
        _save(d)
    _say("自习了「%s」" % topic)
    return learned


def diary(history: list, pet_name: str = "我") -> str:
    """日记：每天写一段（只写一次）"""
    today = time.strftime("%Y-%m-%d")
    if diary_of(today):
        return ""
    convo = _recent_history_text(history, 12)
    if not convo.strip():
        return ""
    txt = _ask(
        "你是%s。用第一人称写一段今天的日记（3~5 句，口语、真诚，可以写心情和印象深的片段，"
        "别写日期、别提 AI/系统）。" % pet_name, convo, max_tokens=400)
    if not txt:
        return ""
    _set_diary(today, txt)
    _say("写好了 %s 的日记" % today)
    return txt


def consolidate(history: list, pet_name: str = "我") -> str:
    """夜间整理：把最近的情节/日记提炼成"值得长期记住的事实"+ 关于主人的画像（每天一次）"""
    d = _load()
    today = time.strftime("%Y-%m-%d")
    if str(d.get("last_consolidate_day") or "") == today:
        return ""
    raw = []
    for e in episodes(60):
        try:
            ts = time.strftime("%m-%d %H:%M", time.localtime(float(e.get("ts") or 0)))
        except Exception:
            ts = ""
        raw.append("%s %s" % (ts, str(e.get("text"))[:100]))
    for day, txt in sorted((d.get("diary") or {}).items())[-3:]:
        raw.append("（%s 的日记）%s" % (day, str(txt)[:150]))
    if not raw:
        d["last_consolidate_day"] = today
        _save(d)
        return ""
    convo = "\n".join(raw)[-3000:]
    out = _ask(
        "你是%s，现在在整理自己的记忆（夜里做的事）。下面是最近发生的事和你的日记。"
        "请做两件事，用 JSON 输出：\"facts\" 是 3~5 条值得长期记住的事"
        "（关于主人的喜好/习惯/正在忙的事，合并重复、丢掉一次性的小事）；"
        "\"profile\" 是 1~4 条对主人的印象（键值对，例如 {\"常做的事\": \"写代码\"}）。"
        "格式：{\"facts\": [\"…\"], \"profile\": {\"键\": \"值\"}}，只输出 JSON。" % pet_name,
        convo, max_tokens=500)
    obj = _json_obj(out)
    facts = [str(x).strip() for x in (obj.get("facts") or []) if str(x).strip()][:6]
    prof = obj.get("profile") or {}
    for f in facts:
        add_note("fact", f)
    if isinstance(prof, dict):
        for k, v in list(prof.items())[:4]:
            set_profile(str(k)[:16], str(v)[:60])
    d = _load()
    d["last_consolidate_day"] = today
    _save(d)
    if facts or prof:
        _say("整理完成：%d 条事实、%d 条画像" % (len(facts), len(prof) if isinstance(prof, dict) else 0))
    return "\n".join(facts)


def maybe_cycle(history: list, pet_name: str = "我", last_user_ts: float = 0.0,
                now: float = None) -> str:
    """定时入口：够间隔、主人不在说话、没超预算 → 挑一件事做（返回做了什么）

    顺序：夜里/日记点之后先写日记 → 每天一次的整理 → 否则归纳记忆 → 再否则自习。
    """
    try:
        if not enabled():
            return ""
        now = float(now if now is not None else time.time())
        if now - _last_cycle[0] < CYCLE_GAP_MIN * 60:
            return ""
        if last_user_ts and (now - float(last_user_ts)) < IDLE_NEED_SEC:
            return ""                     # 主人刚说过话 → 不抢对话
        if not _budget_ok():
            _say("今天的学习次数到顶了（%d 次）" % DAILY_CALL_CAP)
            return ""
        _last_cycle[0] = now
        lt = time.localtime(now)
        did = ""
        if lt.tm_hour >= DIARY_HOUR and not diary_of():
            did = "diary" if diary(history, pet_name) else ""
        if not did:
            d = _load()
            if str(d.get("last_consolidate_day") or "") != time.strftime("%Y-%m-%d", lt):
                did = "consolidate" if consolidate(history, pet_name) else ""
        if not did:
            did = "reflect" if reflect(history, pet_name) else ""
        if not did:
            did = "study" if study(history, pet_name) else ""
        return did
    except Exception as e:
        _say("周期任务失败: %s" % e)
        return ""


def reset_cycle_gap():
    """测试/手动触发用：清掉"刚做过"的时间戳"""
    _last_cycle[0] = 0.0


if __name__ == "__main__":
    _say("开关: %s（config.json → learn_enabled）" % enabled())
    _say("存储: %s" % _store_path())
    _say("")
    if len(sys.argv) > 1 and sys.argv[1] == "note":
        _say(memory_note(" ".join(sys.argv[2:]) or "") or "（还没有记忆）")
    else:
        _say(summary_text())
