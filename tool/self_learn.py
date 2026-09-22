# -*- coding: utf-8 -*-
"""自主学习：让她自己记住东西、自己学点东西、自己写日记。

开关：右键菜单 →「自主学习（自己记东西）」→ config.json 的 learn_enabled

三件事（都写进 pets/<角色>/memory/learned.json，可以随时打开来看）：

1. **归纳记忆**：聊完一段，她自己提炼"关于主人的事"（喜好、习惯、正在忙什么）
   和"我自己的心情"，存成长期记忆；以后聊天会带上这些记忆（不用每次重问）。
2. **自习**：主人不在的时候，她挑一个话题（上次没搞懂的、主人提过的、或者
   她自己好奇的）让模型给她讲一小段，存成"我学到的东西"。这就是"自主学习"。
3. **日记**：每天写一段，记今天聊了什么、心情如何。

省钱/防打扰：
    * 一次只做一件事，间隔默认 20 分钟；主人最近 3 分钟说过话就不做（不抢对话）
    * 每次只调用一次小请求（≤400 token），一天最多 40 次
    * 全部在后台线程里跑，失败只写日志，绝不打断桌宠
"""
import json
import os
import time

MAX_NOTES = 400                 # 长期记忆上限（超过就丢最旧的"知识类"）
CYCLE_GAP_MIN = 20              # 两次自主学习的最小间隔（分钟）
IDLE_NEED_SEC = 180             # 主人多久没说话才算"空闲"
DIARY_HOUR = 21                 # 这个点之后写今天的日记
DAILY_CALL_CAP = 40             # 一天的模型调用上限（保险丝）

_last_cycle = [0.0]
_last_call_day = ["", 0]        # (日期, 次数)


def _cfg_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def _log(msg: str):
    try:
        print(f"[学习] {msg}")
    except Exception:
        pass
    try:
        p = os.path.join("data", "self_learn.log")
        os.makedirs("data", exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ─────────────────────── 开关 ───────────────────────

def enabled() -> bool:
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("learn_enabled", "false")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def set_enabled(on: bool) -> bool:
    try:
        from tool.config import get_config
        cfg = dict(get_config("./config.json") or {})
        cfg["learn_enabled"] = "true" if on else "false"
        p = _cfg_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _log(f"自主学习 → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        _log(f"⚠ 开关写入失败: {e}")
        return False


# ─────────────────────── 存储 ───────────────────────

def _store_path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = os.path.join("memory")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "learned.json")


def _load() -> dict:
    p = _store_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("notes"), list):
            return d
    except Exception:
        pass
    return {"notes": [], "diary": {}, "topic_ideas": []}


def _save(d: dict):
    p = _store_path()
    try:
        notes = d.get("notes") or []
        if len(notes) > MAX_NOTES:
            # 先丢最旧的"知识类"，主人的事（fact）和日记优先保留
            keep = [n for n in notes if n.get("kind") != "knowledge"]
            drop = sorted([n for n in notes if n.get("kind") == "knowledge"],
                          key=lambda n: n.get("ts", 0))
            need = MAX_NOTES - len(keep)
            d["notes"] = sorted(keep + drop[-max(0, need):], key=lambda n: n.get("ts", 0))
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        _log(f"⚠ 记忆写入失败: {e}")


def add_note(kind: str, text: str, topic: str = "") -> bool:
    text = str(text or "").strip()
    if not text:
        return False
    d = _load()
    d.setdefault("notes", []).append({
        "ts": time.time(), "kind": kind, "topic": topic, "text": text[:600],
    })
    _save(d)
    _log(f"记下一条（{kind}）：{text[:60]}")
    return True


def notes(kind: str = "") -> list:
    ns = _load().get("notes") or []
    return [n for n in ns if (not kind or n.get("kind") == kind)]


def diary_of(day: str = "") -> str:
    day = day or time.strftime("%Y-%m-%d")
    return str((_load().get("diary") or {}).get(day) or "")


def _set_diary(day: str, text: str):
    d = _load()
    d.setdefault("diary", {})[day] = str(text or "")[:800]
    # 日记只留最近 60 天
    try:
        items = sorted((d["diary"] or {}).items())
        if len(items) > 60:
            d["diary"] = dict(items[-60:])
    except Exception:
        pass
    _save(d)


def summary_text(limit: int = 10) -> str:
    """给人看的一页摘要（菜单里点「看看她学到了什么」时用）"""
    d = _load()
    ns = (d.get("notes") or [])[-limit:]
    lines = ["她的长期记忆（最近 %d 条）：" % len(ns)]
    for n in ns:
        tag = {"fact": "关于主人", "knowledge": "学到", "diary": "心情"}.get(n.get("kind"), "记")
        lines.append("· [%s] %s" % (tag, str(n.get("text"))[:120]))
    ds = sorted((d.get("diary") or {}).items())[-3:]
    for day, txt in ds:
        lines.append("· 日记(%s)：%s" % (day, txt[:140]))
    if len(lines) == 1:
        lines.append("（还没有，开启「自主学习」后她会自己开始记）")
    return "\n".join(lines)


# ─────────────────────── 给聊天用的记忆注入 ───────────────────────

def memory_note(user_text: str = "", limit: int = 6) -> str:
    """拼一段"你记住的事"交给模型（和主人这句话相关的优先）"""
    try:
        if not enabled():
            return ""
        ns = notes()
        if not ns:
            return ""
        u = str(user_text or "")
        scored = []
        for n in ns:
            t = str(n.get("text") or "")
            score = n.get("ts", 0) / 1e9        # 新的略优先
            if u:
                for w in _keywords(t):
                    if w and w in u:
                        score += 1.5
            if n.get("kind") == "fact":
                score += 0.4
            scored.append((score, t, n.get("kind")))
        scored.sort(key=lambda x: -x[0])
        picked = [s for s in scored[:limit] if s[1].strip()]
        if not picked:
            return ""
        body = "\n".join("· " + s[1][:160] for s in picked)
        txt = ("【你记住的事（长期记忆，自然使用，不要念出来）】\n" + body)
        day = diary_of()
        if day:
            txt += "\n【今天的日记（你自己写的）】" + day[:200]
        return txt
    except Exception:
        return ""


def _keywords(text: str, n: int = 6) -> list:
    """粗糙关键词：中文按 2 字滑窗，英文按单词（够用来做相关度了）"""
    import re
    out = []
    try:
        for m in re.finditer("[A-Za-z]{3,}", text):
            out.append(m.group(0).lower())
        zh = re.sub("[^\\u4e00-\\u9fff]", "", text)
        for i in range(len(zh) - 1):
            out.append(zh[i:i + 2])
    except Exception:
        pass
    return out[:40]


def _recent_history_text(history: list, n: int = 8) -> str:
    """把最近几轮对话拼成纯文本，喂给"归纳"用"""
    lines = []
    try:
        for m in (history or [])[-n:]:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            if role not in ("user", "assistant"):
                continue
            c = str(m.get("content") or "").strip()
            if not c:
                continue
            who = "主人" if role == "user" else "我"
            lines.append(f"{who}：{c[:220]}")
    except Exception:
        pass
    return "\n".join(lines)


# ─────────────────────── 模型调用 ───────────────────────

def _budget_ok() -> bool:
    day = time.strftime("%Y-%m-%d")
    if _last_call_day[0] != day:
        _last_call_day[0], _last_call_day[1] = day, 0
    return _last_call_day[1] < DAILY_CALL_CAP


def _ask(system: str, user: str, max_tokens: int = 400) -> str:
    """问她当前用的那个模型（云端优先，本地也能用）。失败返回空串。"""
    if not _budget_ok():
        return ""
    try:
        from tool.config import get_config
        model_type = str(get_config("./config.json").get("model_type", "deepseek"))
    except Exception:
        model_type = "deepseek"
    try:
        if model_type == "local":
            from tool.chat import ollama_post
            r = ollama_post("qwen3:14b", {"model": "qwen3:14b",
                                          "prompt": system + "\n\n" + user,
                                          "stream": False, "options": {"num_predict": max_tokens}})
            txt = ""
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
        _log(f"⚠ 调用失败: {type(e).__name__}: {e}")
        return ""


def _json_list(text: str) -> list:
    """从模型回复里抠出 JSON 列表"""
    import re
    s = str(text or "").strip()
    s = re.sub("^```(?:json)?|```$", "", s, flags=re.M).strip()
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return [str(x) for x in d]
        if isinstance(d, dict):
            return [str(v) for v in d.values()]
    except Exception:
        pass
    m = re.search("\\[.*\\]", s, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            if isinstance(d, list):
                return [str(x) for x in d]
        except Exception:
            pass
    return [s] if s else []


# ─────────────────────── 三件事 ───────────────────────

def reflect(history: list, pet_name: str = "我") -> int:
    """归纳刚才的对话 → 存长期记忆（关于主人的事实 + 自己的心情）"""
    convo = _recent_history_text(history)
    if len(convo) < 30:
        return 0
    out = _ask(
        f"你是{pet_name}。下面是你和主人的对话记录。请提炼值得长期记住的东西："
        "1) 关于主人的事实/喜好/习惯/正在忙的事（最多 2 条）；"
        "2) 你自己此刻的心情（1 条，第一人称短句）。"
        "只输出 JSON 列表，每一项以「事实：」或「心情：」开头，比如"
        "[\"事实：主人喜欢喝冰美式\",\"心情：今天被他夸了，有点得意\"]。没有值得记的就输出 []。",
        convo, max_tokens=300)
    items = _json_list(out)
    n = 0
    for it in items:
        it = str(it).strip()
        if not it or it in ("[]", "{}"):
            continue
        if it.startswith("心情："):
            n += int(add_note("diary", it[3:].strip()))
        elif it.startswith("事实："):
            n += int(add_note("fact", it[3:].strip()))
        else:
            n += int(add_note("fact", it))
    return n


def study(history: list, pet_name: str = "我") -> str:
    """自习：挑一个话题，让模型讲一小段，存成"我学到的东西"。

    话题优先级：① 上次记的"想了解"；② 最近对话里出现过的、自己不熟的东西；③ 默认好奇心列表。
    """
    d = _load()
    topic = ""
    ideas = d.get("topic_ideas") or []
    if ideas:
        topic = str(ideas.pop(0))
        d["topic_ideas"] = ideas
        _save(d)
    if not topic:
        convo = _recent_history_text(history, 6)
        topic = _ask(
            f"你是{pet_name}。从下面的对话里挑一个你（作为角色）会好奇、值得自己去了解一下的话题，"
            "只输出这个话题本身（10 字以内），不要解释，不要引号；实在没有就输出「天气与季节变化」。",
            convo or "（今天没什么对话）", max_tokens=40).strip().strip("「」\"'。")
        topic = topic.splitlines()[0][:20] if topic else ""
    if not topic:
        return ""
    body = _ask(
        f"你是{pet_name}，正在自己偷偷补课。请用一个 16 岁少女的口吻，"
        "把这个话题里最值得知道的 2~3 件事讲给自己听（不超过 120 字，像写在笔记本上，"
        "不要提问、不要客套、不要提到 AI 或模型）：",
        topic, max_tokens=300)
    body = body.strip()
    if not body:
        return ""
    add_note("knowledge", body, topic=topic)
    return topic


def diary(history: list, pet_name: str = "我") -> str:
    """日记：每天一段（21 点后、当天还没写过才写）"""
    day = time.strftime("%Y-%m-%d")
    if diary_of(day):
        return ""
    if time.localtime().tm_hour < DIARY_HOUR:
        return ""
    convo = _recent_history_text(history, 12)
    if len(convo) < 20:
        convo = "（今天主人没怎么跟我说话）"
    out = _ask(
        f"你是{pet_name}。请用 2~3 句第一人称写今天的日记（少女口吻，可以带一点小情绪），"
        "只写日记正文，不要日期、不要引号、不要解释：",
        convo, max_tokens=300)
    out = out.strip().strip("「」\"'")
    if out:
        _set_diary(day, out)
        add_note("diary", out)
        _log(f"写完日记：{out[:60]}")
    return out


def maybe_cycle(history: list, pet_name: str = "我", last_user_ts: float = 0.0,
                has_model: bool = True) -> str:
    """主循环调用：到点、空闲、开着开关 → 干一件（归纳 / 自习 / 日记）。

    返回做了什么的说明（没做返回空串）。调用方应放到后台线程里，别卡界面。
    """
    try:
        if not enabled() or not has_model:
            return ""
        now = time.time()
        if now - float(_last_cycle[0] or 0) < CYCLE_GAP_MIN * 60:
            return ""
        if last_user_ts and (now - float(last_user_ts)) < IDLE_NEED_SEC:
            return ""          # 主人刚说过话，别抢
        _last_cycle[0] = now
        if diary(history, pet_name):
            return "日记"
        convo = _recent_history_text(history, 10)
        # 有余力时优先归纳（对话有内容），否则自习
        if len(convo) > 200 and not _load().get("_last_reflect_day") == time.strftime("%Y-%m-%d"):
            n = reflect(history, pet_name)
            d = _load()
            d["_last_reflect_day"] = time.strftime("%Y-%m-%d")
            _save(d)
            if n:
                return f"归纳 {n} 条"
        t = study(history, pet_name)
        return ("自习：" + t) if t else ""
    except Exception as e:
        _log(f"⚠ 学习循环出错: {type(e).__name__}: {e}")
        return ""


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("开关:", enabled())
    print("记忆文件:", _store_path())
    print()
    print("关键词:", _keywords("主人今天在调 AIpet 桌宠的键鼠功能")[:12])
    print("相关记忆注入:")
    print(memory_note("键鼠 桌宠")[:300] or "（空）")
    print()
    print(summary_text())
