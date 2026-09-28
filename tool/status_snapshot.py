# -*- coding: utf-8 -*-
"""把她此刻的现状收成一页（**纯数据，不碰 Qt**）。

为什么单独一层
--------------
「她的状态」要显示 9 个内心模块（心情好感 / 习惯 / 开口时机 / 动机 / 关怀 / 提醒 /
任务经验 / 自主分档 / 自主学习）的东西。取数如果直接写在窗口代码里会有两个毛病：
  1) 任何一个模块出问题（存盘损坏、依赖缺失、字段改名）都会让整个窗口崩掉或空白；
  2) 想验证"窗口显示的是不是真实数据"就必须开 GUI。
所以这里只做**取数 + 归一化**，返回纯 dict；窗口（classes/status_window.py）只负责画。
`as_text()` 还能把这一页直接变成一段文字（复制给主人 / 贴进 bug 报告）。

两条口径
--------
* 每一段独立 try/except：坏一个只少那一张卡，而且**如实把坏因写在卡上** ——
  不是静默留空（静默留空会让人以为"她本来就没这回事"）。
* 每个取数函数都用 getattr 兜一下：模块改名/删函数时窗口不会炸，只会显示这一项取不到。
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 卡片里的样式名（窗口层映射成颜色；数据层不关心颜色）
TAG_RED = "red"        # 心情 / 关系这类要紧数
TAG_GOLD = "gold"      # 陪伴天数 / 活跃度这类
TAG_PLAIN = "plain"


def _clip(text, limit: int = 400) -> str:
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit] + "…（还有 %d 字）" % (len(s) - limit)


def _why(why) -> str:
    """把失败原因包成"（原因）"；没有原因就返回空串（别拼出难看的「（）」）"""
    w = str(why or "").strip()
    return "（%s）" % w if w else ""


def _try(desc: str, fn, *a, **k):
    """调用一个取数函数；失败返回 (None, "人话原因")。

    ⚠ 失败原因要带出来：以前这类地方喜欢 `except Exception: pass`，结果主人只看到
      "这项没有内容"，根本不知道是模块坏了。
    """
    try:
        return fn(*a, **k), ""
    except Exception as e:
        return None, "%s（%s: %s）" % (desc, type(e).__name__, str(e)[:80])


def _mod(name: str):
    """延迟导入某个内心模块（导入失败也返回 None，不抛）"""
    try:
        return __import__("tool.%s" % name, fromlist=["x"])
    except Exception:
        return None


def _call(mod, fname: str, *a, **k):
    """取模块里的函数并调用；模块/函数取不到都返回 (None, 原因)"""
    if mod is None:
        return None, "模块导入失败"
    fn = getattr(mod, fname, None)
    if fn is None:
        return None, "没有 %s()" % fname
    return _try(fname + "()", fn, *a, **k)


def _card(title: str, body: str = "", tags=None, error: bool = False) -> dict:
    return {"title": str(title), "body": _clip(body), "tags": list(tags or []),
            "error": bool(error)}


def _err_card(title: str, why: str) -> dict:
    return _card(title, "取不到：%s" % why, [(("取不到"), TAG_PLAIN)], error=True)


# ── 各页 ───────────────────────────────────────────────
def section_now() -> dict:
    """第 1 页：现在（心情/关系/陪伴天数/活跃度 这些一眼要看到的）"""
    tags, cards = [], []
    st = _mod("state")
    care = _mod("care")
    dz = _mod("desire")
    sl = _mod("self_learn")

    v, why = _call(st, "mood")
    if v is None and why:
        cards.append(_err_card("心情 / 关系", why))
    else:
        mv = int(v or 0)
        av, _ = _call(st, "affinity")
        ml, _ = _call(st, "mood_label")
        tags.append(("心情 %d%s" % (mv, ("·%s" % ml) if ml else ""), TAG_RED))
        if av is not None:
            tags.append(("关系 %.1f" % float(av), TAG_RED))

    v, _ = _call(care, "companion_days")
    if v:
        tags.append(("在一起第 %d 天" % int(v), TAG_GOLD))
    v, _ = _call(care, "meeting_mode")
    if v:
        tags.append(("会议静音中", TAG_GOLD))
    v, _ = _call(care, "quiet_now")
    if v:
        tags.append(("深夜安静中", TAG_GOLD))
    v, _ = _call(dz, "level_label")
    if v:
        tags.append(("活跃度 %s" % v, TAG_GOLD))

    body = []
    v, _ = _call(st, "summary")
    if v:
        body.append("【她的状态】" + str(v))
    v, why = _call(st, "last_talk_ago")
    # ⚠ 没聊过时 last_talk_ago() 给的是 1e9 哨兵值（state.summary 里已经写了"还没聊过"），
    #   直接显示会变成"1000000000.0 小时前"
    if v is not None and float(v) < 24 * 30:
        body.append("【上次说话】%.1f 小时前" % float(v))
    v, _ = _call(sl, "working")
    if v:
        body.append("【手上的事】%s%s" % (str(v.get("task"))[:70],
                                        "（做成了）" if v.get("ok") else "（没做成）"))
    if body:
        cards.append(_card("现在", "\n".join(body), []))

    v, why = _call(dz, "summary_text")
    cards.append(_card("她现在的念头", v if v else "取不到%s" % _why(why), [], error=not v))
    v, why = _call(care, "summary_text")
    cards.append(_card("陪伴与关怀", v if v else "取不到%s" % _why(why), [], error=not v))
    return {"key": "now", "title": "现在", "tags": tags, "cards": cards}


def section_habits() -> dict:
    """第 2 页：习惯（作息 / 活跃时段 / 常用软件 / 常听的歌）"""
    cards = []
    hb = _mod("habits")
    v, why = _call(hb, "hours_text")
    cards.append(_card("作息与活跃", v if v else "还没攒够数据%s" % _why(why), [],
                       error=bool(why)))
    v, why = _call(hb, "schedule_text")
    cards.append(_card("这些天几点在电脑前", v if v else "还没攒够数据%s" % _why(why), [],
                       error=bool(why)))
    v, why = _call(hb, "apps_text")
    cards.append(_card("常用软件", v if v else "还没认出来的软件%s" % _why(why), [],
                       error=bool(why)))
    v, _ = _call(hb, "music_text")
    if v:
        cards.append(_card("常听的歌", v))
    v, _ = _call(hb, "enabled")
    if v is False:
        cards.insert(0, _card("提示", "习惯采集是关着的（config.json 的 habits_enabled）"))
    return {"key": "habits", "title": "习惯", "tags": [], "cards": cards}


def section_mind() -> dict:
    """第 3 页：心里（开口时机 / 动机 / 自主分档）"""
    cards = []
    at = _mod("attention")
    if at is not None:
        lines, miss = [], []
        v, why = _call(at, "enabled")
        lines.append("开口时机打分：%s" % ("开着" if v else "关着（她不会主动搭话）"))
        v, why = _call(at, "threshold")
        if v is not None:
            lines.append("开口阈值：%.1f 分" % float(v))
        else:
            miss.append("threshold" + _why(why))
        v, why = _call(at, "score")
        if isinstance(v, (list, tuple)) and v:
            # score() 返回 (分数, 理由)：光给一个数字主人看不出所以然
            extra = str(v[1])[:40] if len(v) > 1 else ""
            lines.append("此刻得分：%.1f%s" % (float(v[0]), ("（%s）" % extra) if extra else ""))
        elif v is not None:
            lines.append("此刻得分：%.1f" % float(v))
        else:
            miss.append("score" + _why(why))
        v, why = _call(at, "speaks_last_hour")
        if v is not None:
            lines.append("最近一小时开口：%d 次" % int(v))
        else:
            miss.append("speaks_last_hour" + _why(why))
        # 取不到的项要写出来：静默少一行会让人以为"本来就没这项"
        if miss:
            lines.append("取不到的项：" + "、".join(miss))
        cards.append(_card("开口时机", "\n".join(lines)))
    else:
        cards.append(_err_card("开口时机", "模块导入失败"))

    dz = _mod("desire")
    v, why = _call(dz, "summary_text")
    lines = [v] if v else []
    w, _ = _call(dz, "wants")
    if w:
        if isinstance(w, dict):
            # wants() 给的是 {动机: 强度} 这种字典，直接 join 会打印出键名
            lines.append("现在想要：" + "、".join("%s %.0f" % (k, float(v))
                                              for k, v in w.items() if float(v or 0) > 0)
                         if any(float(x or 0) > 0 for x in w.values()) else "现在没什么特别想要的")
        elif isinstance(w, (list, tuple)):
            lines.append("现在想要：" + "、".join(str(x) for x in w))
        else:
            lines.append("现在想要：%s" % w)
    cards.append(_card("动机（无聊 / 想说话 / 精力）",
                       "\n".join([x for x in lines if x]) or "取不到%s" % _why(why),
                       [], error=not lines))

    au = _mod("autonomy")
    v, why = _call(au, "summary_text")
    lv, _ = _call(au, "level_label")
    cards.append(_card("自主行动分档（%s）" % (lv or "?"),
                       v if v else "取不到：%s" % why, [], error=not v))
    return {"key": "mind", "title": "心里", "tags": [], "cards": cards}


def section_remind() -> dict:
    """第 4 页：提醒（待办清单 / 番茄钟）"""
    cards = []
    rm = _mod("reminder")
    v, why = _call(rm, "summary_text")
    cards.append(_card("提醒与待办", v if v else "取不到：%s" % why, [], error=not v))
    v, why = _call(rm, "list_text")
    if v:
        cards.append(_card("清单", v))
    items, _ = _call(rm, "items")
    if isinstance(items, (list, tuple)):
        due, _ = _call(rm, "due")
        n_due = len(due) if isinstance(due, (list, tuple)) else 0
        cards.append(_card("统计", "共 %d 条，到点的 %d 条" % (len(items), n_due)))
    v, _ = _call(rm, "enabled")
    if v is False:
        cards.insert(0, _card("提示", "提醒功能关着（config.json 的 reminder_enabled）"))
    return {"key": "remind", "title": "提醒", "tags": [], "cards": cards}


def section_memory() -> dict:
    """第 5 页：记忆（她自己学的东西 / 画像 / 任务经验 / 日记）"""
    cards = []
    sl = _mod("self_learn")
    v, why = _call(sl, "summary_text")
    cards.append(_card("她的长期记忆", v if v else "取不到%s" % _why(why), [], error=not v))
    v, _ = _call(sl, "enabled")
    if v is False:
        cards.insert(0, _card("提示", "自主学习是关着的（config.json 的 learn_enabled）；"
                                      "右键「📖 自主学习」可以打开"))
    v, why = _call(sl, "profile_text")
    cards.append(_card("她对主人的画像", v if v else "还没攒出画像%s" % _why(why), []))
    v, why = _call(sl, "diary_of")
    cards.append(_card("今天的日记", v if v else "今天还没写日记%s" % _why(why), []))
    ex = _mod("experience")
    v, why = _call(ex, "summary_text")
    cards.append(_card("任务经验（下次先查这个）", v if v else "还没有经验%s" % _why(why), [],
                       error=bool(why)))
    return {"key": "memory", "title": "记忆", "tags": [], "cards": cards}


PAGES = (section_now, section_habits, section_mind, section_remind, section_memory)
# 整页炸掉时的兜底标题（别把函数名当成页名显示给主人）
PAGE_TITLES = {"section_now": "现在", "section_habits": "习惯", "section_mind": "心里",
               "section_remind": "提醒", "section_memory": "记忆"}


def subtitle(pages=None) -> str:
    """一行副标题：把她最要紧的几个数拼起来（取不到就跳过）"""
    pages = pages if pages is not None else [p() for p in PAGES]
    for p in pages:
        if p.get("key") == "now":
            tags = [t[0] for t in p.get("tags") or []]
            if tags:
                return " · ".join(tags)
    return "她此刻的状态"


def snapshot() -> dict:
    """采集全部页面。任何一页整体炸掉也只影响那一页。"""
    pages = []
    for fn in PAGES:
        try:
            pages.append(fn())
        except Exception as e:
            pages.append({"key": fn.__name__,
                          "title": PAGE_TITLES.get(fn.__name__, fn.__name__),
                          "tags": [], "cards": [_err_card("这一页", "%s: %s"
                                                          % (type(e).__name__, str(e)[:120]))]})
    return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "subtitle": subtitle(pages), "pages": pages}


def as_text(snap: dict = None) -> str:
    """把这一页摊成一段纯文字（复制给主人 / 贴进报告都方便）"""
    snap = snap if isinstance(snap, dict) else snapshot()
    out = ["【她的状态】%s" % snap.get("subtitle", ""),
           "（%s 采集）" % snap.get("generated_at", "")]
    for p in snap.get("pages") or []:
        out.append("")
        out.append("── %s ──" % p.get("title", ""))
        if p.get("tags"):
            out.append("   " + " · ".join(t[0] for t in p["tags"]))
        for c in p.get("cards") or []:
            body = str(c.get("body") or "").replace("\n", "\n     ")
            out.append("【%s】" % c.get("title", ""))
            if body.strip():
                out.append("     " + body)
            for t in c.get("tags") or []:
                out.append("     # " + t[0])
    return "\n".join(out)


def data_dir() -> str:
    """她的数据目录（内存文件都在这里；窗口上的「打开数据目录」用它）"""
    for mod_name, fname in (("tool.paths", "get_memory_dir"),):
        try:
            mod = __import__(mod_name, fromlist=["x"])
            fn = getattr(mod, fname, None)
            if fn:
                return str(fn())
        except Exception:
            pass
    try:
        from tool import state as _st          # 私有但稳定：它知道 memory 目录在哪
        return os.path.dirname(str(_st._store_path()))
    except Exception:
        return os.path.join(APP, "pets")


if __name__ == "__main__":
    print(as_text())
