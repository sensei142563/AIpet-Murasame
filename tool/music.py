# -*- coding: utf-8 -*-
"""网易云音乐的完整控制系统（全部走 UI Automation：后台操作、不切窗口、不动鼠标）。

她能做的（写一行标记就行）：
    【音乐】播放 歌名 歌手       搜索并播放（后台：写搜索框 → 按 search → 按第一条的播放）
    【音乐】暂停 / 继续          播放·暂停切换
    【音乐】下一首 / 上一首
    【音乐】单曲循环 / 列表循环 / 随机播放 / 顺序播放
    【音乐】我喜欢              播放「我喜欢的音乐」
    【音乐】播放歌单 <名字>      切到某个歌单并播放全部
    【音乐】收藏 / 歌词 / 静音
    【音乐】在放什么            现在放的是什么、在不在放

实现要点（都是在这台机器上实测出来的结论）：
  · 网易云是 CEF 界面：MSAA 只能拿到窗口层，**UIA 树是完整的**（UIA 需要 comtypes）。
  · 播放条按钮的 name 就是功能名：play / next / pre / collect / lyric / Volume1 / playlist；
    循环方式按钮的 name 会在 shuffle → order → loop → singleloop 之间变，
    所以"设成单曲循环"就是**按到 name 变成 singleloop 为止**。
  · 侧边栏「我喜欢的音乐」的 AutomationId 是 left_nav_myFav；歌单页上有「播放全部」按钮。
  · 全程不需要焦点（SetValue / Invoke 都是后台调用）—— 这就是主人要的"不显示窗口执行"。
  · 播放真实性校验：窗口标题 = 当前歌曲；播放进度（滑块数值）在变 = 真的在放。
  · UIA 不可用（没装 comtypes）时退回系统媒体键，并如实说明。
"""
import ctypes
import json
import os
import re
import time

MUSIC_MARK = "【音乐】"
_WINDOW_CLASS = "OrpheusBrowserHost"
_SEARCH_URL = "https://music.163.com/api/search/get"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_APP_HINTS = (
    os.path.expandvars(r"%ProgramFiles(x86)%\NetEase\CloudMusic\cloudmusic.exe"),
    os.path.expandvars(r"%ProgramFiles%\NetEase\CloudMusic\cloudmusic.exe"),
    os.path.expandvars(r"%LocalAppData%\NetEase\CloudMusic\cloudmusic.exe"),
)

_LINE = re.compile("[【\\[]\\s*音乐\\s*[】\\]]\\s*([^\"\\]\\n]{1,80})")

# 同一个音乐操作同时只能跑一个（她连着催时，两个自动化会互相抢）
_busy = [False]
_notes = []          # 本次操作的"要告诉主人的话"（静音已解除/踹通了播放…）


def _note(text: str):
    if text:
        try:
            _notes.append(str(text))
        except Exception:
            pass


def take_notes() -> str:
    """取出并清空这次操作攒下的提示（play_song 汇报时带上）"""
    try:
        out = "".join(_notes)
        _notes.clear()
        return out
    except Exception:
        return ""
# 每首歌的尝试时间戳：短时间内试太多次就不再试，免得"一直重复搜索"
_attempts = {}
_ATTEMPT_WINDOW = 600       # 10 分钟内最多试几次
_ATTEMPT_LIMIT = 4
_ATTEMPT_GAP = 8.0          # 两次尝试之间至少隔几秒（防疯狂连点，但不用主人干等）
# 歌单列表缓存（读侧边栏要零点几秒，不必每轮都读）
_playlists_cache = {"t": 0.0, "v": []}
_PLAYLIST_TTL = 60.0

# 循环方式：按钮 name ↔ 说法
_LOOP_MODES = {"singleloop": "单曲循环", "loop": "列表循环",
               "shuffle": "随机播放", "order": "顺序播放"}


def _log(msg: str):
    try:
        print(f"[音乐] {msg}")
    except Exception:
        pass


def prompt_rules() -> str:
    """交给模型的能力说明（自动带上主人的歌单 + 她记住的听歌口味）"""
    pls = list_playlists()
    pl_line = ""
    if pls:
        pl_line = "主人的歌单（可以自己挑着放）：" + "、".join(pls[:8]) + "。\n"
    fav = favorites_text(6)
    fav_line = ("主人常听的（她想主动放歌时优先从这些里挑）：" + fav + "。\n") if fav else ""
    mine = own_taste_text(6)
    mine_line = ("你自己挑过、爱听的：" + mine + "（想听就说【音乐】我想听）。\n") if mine else ""
    return (
        "【音乐控制（网易云，已开启）】你可以自己操作网易云音乐，在回复里单独写一行：\n"
        "【音乐】播放 歌名 歌手（例如【音乐】播放 沦陷 dj）\n"
        "【音乐】暂停 / 继续 / 下一首 / 上一首\n"
        "【音乐】单曲循环 / 列表循环 / 随机播放 / 顺序播放\n"
        "【音乐】我喜欢（放**主人收藏的那个歌单**）／【音乐】播放歌单 名字\n"
        "★★ 两种「喜欢」要分清（很容易搞混）：\n"
        "   ① 主人说「放**我**喜欢的音乐」→ 那是**网易云里他收藏的那个歌单的名字**，"
        "用【音乐】我喜欢。回话要说清是他的：「你收藏的那张歌单给你放上了」。\n"
        "   ② 主人说「放**你**喜欢的音乐」「放你想听的」「点一首你爱听的」→ "
        "**是让你自己挑**！按你自己的人设口味选一首（清冷、安静一点的都行），"
        "自己写【音乐】播放 歌名 歌手，然后说一句**你自己**为什么想听这首"
        "（比如「今天想听这首，陪我一起吧」）。**这种情况绝对不要用【音乐】我喜欢** —— "
        "那会把主人的歌单放成他的收藏，主人会以为你没听懂。\n"
        "【音乐】我想听 歌名 歌手（放**你自己想听**的，会记进你的口味）／【音乐】我想听（放你挑过的一首）\n"
        "【音乐】收藏 / 歌词 / 静音 / 在放什么 / 关弹窗 / 爱听什么\n"
        + pl_line + fav_line + mine_line +
        "★ 这些都是**后台执行**：不切走主人的画面、不动鼠标，放心用。\n"
        "★ **记住版本**：同一首歌有很多版本（原唱/翻唱/remix/现场）。桌宠会记住"
        "主人听过、爱听的那一版，下次点同一首歌**优先放他爱听的那版**；"
        "他问「我爱听什么」时，用【音乐】爱听什么 查出来念给他听。\n"
        "★ **会员曲的事**：主人没有黑胶 VIP（点会员曲只会放 30 秒试听，还会弹开通页面）。"
        "所以点歌时桌宠会**优先挑不用会员的版本**（免费 / 低音质免费）。"
        "如果一首歌只有会员版，桌宠会告诉你——你就如实跟主人说「这首要会员，只有试听，"
        "要不要换一首免费的同名版本」，别硬说放好了。\n"
        "★ 会员/广告弹窗（开通黑胶VIP、收银台、活动页）桌宠会**自动点掉**；"
        "主人明确说「关弹窗」时可以用【音乐】关弹窗。\n"
        "★ **点名某首歌时不要整单播放**：主人说「放我喜欢的音乐里的《X》」"
        "「歌单里的那首 X」时，用【音乐】播放 X（**不是**【音乐】我喜欢）——"
        "整单播放会放到歌单里存的那一版，而那版常常是要会员的（只能试听）。\n"
        "★ 主人说「帮我点歌」「放一首…」「换首歌」「暂停」「单曲循环」时就用它，"
        "不要自己去点搜索框猜坐标。\n"
        "★ 一次只做一件事；做完用你自己的话跟主人说一声。\n"
        "★ 自主模式下（主人没开口）你也可以**想放什么就放什么**：他同一首听很久了、"
        "或者看不出在忙什么，就给他换一首合适的；但别太频繁，一次会话换一两次就够。\n"
        "★ 如果桌宠说「没放上 / 没做成」，不要自己重复点歌（重复请求会被拒绝）："
        "如实跟主人说没做成，或者等他再喊你。\n"
        "★ 标记那一行不会念出来，也不会显示给主人看。"
    )


def _norm(s: str) -> str:
    return re.sub("\\s+", " ", str(s or "")).strip()


# ─────────────────────── 解析 ───────────────────────

def parse(text: str) -> list:
    """解析【音乐】标记 → [(动作, 参数)]"""
    out = []
    for m in _LINE.finditer(str(text or "")):
        s = _norm(m.group(1)).strip("：:，,。")
        if not s:
            continue
        low = s.lower()
        if any(k in s for k in ("暂停", "停一下", "pause")) or s == "停":
            out.append(("pause", ""))
        elif any(k in s for k in ("继续", "接着放", "resume")):
            out.append(("resume", ""))
        elif any(k in s for k in ("下一首", "下首", "下一曲", "切歌", "next")):
            out.append(("next", ""))
        elif any(k in s for k in ("上一首", "上首", "上一曲", "prev")):
            out.append(("prev", ""))
        elif any(k in s for k in ("单曲循环", "单曲")):
            out.append(("loop_single", ""))
        elif any(k in s for k in ("列表循环", "循环播放", "循环")):
            out.append(("loop_list", ""))
        elif any(k in s for k in ("随机", "乱序", "shuffle")):
            out.append(("loop_random", ""))
        elif any(k in s for k in ("顺序播放", "顺序", "order")):
            out.append(("loop_order", ""))
        elif s.startswith("我想听") or s.startswith("自己想听") or s.startswith("放我想听的"):
            # 「我想听」= **她自己挑的歌**（和「我喜欢」= 主人收藏的歌单要分开；
            # 用户反馈过：让她放她自己喜欢的音乐，回复却成了主人的歌单 ✗）
            q = re.sub("^(我想听|自己想听|放我想听的)", "", s).strip("：:，,。\"'「」")
            out.append(("mine", q))
        elif any(k in s for k in ("我喜欢", "喜欢的歌", "收藏的歌")):
            out.append(("liked", ""))
        elif s.startswith("播放歌单") or s.startswith("切歌单") or s.startswith("换个歌单"):
            q = re.sub("^(播放歌单|切歌单|换个歌单|换歌单)", "", s).strip("：:，,。\"'「」")
            out.append(("playlist", q))
        elif any(k in s for k in ("收藏", "喜欢这首", "红心")):
            out.append(("favorite", ""))
        elif "歌词" in s:
            out.append(("lyric", ""))
        elif any(k in s for k in ("静音", "音量")):
            out.append(("mute", ""))
        elif any(k in s for k in ("在放什么", "放的是什么", "当前歌曲", "现在放的", "状态")):
            out.append(("now", ""))
        elif any(k in s for k in ("关弹窗", "关掉弹窗", "弹窗", "关广告", "关掉广告", "关掉会员")):
            out.append(("close_popup", ""))
        elif any(k in s for k in ("爱听什么", "爱听", "常听什么", "常听的", "听歌口味", "喜欢听什么")):
            out.append(("favorites", ""))
        elif s.startswith("播放") or s.startswith("放") or s.startswith("点歌") or low.startswith("play"):
            q = re.sub("^(播放|放一首|放|点歌|点一首|play|放一下)", "", s).strip("：:，,。\"'「」")
            if q:
                out.append(("play", q))
        elif s.startswith("搜索") or s.startswith("搜"):
            q = re.sub("^(搜索|搜一首|搜)", "", s).strip("：:，,。\"'「」")
            if q:
                out.append(("search", q))
    return out[:2]


def strip(text: str) -> str:
    """把标记行从台词里去掉"""
    src = str(text or "")
    try:
        if not _LINE.search(src):
            return src
        return re.sub("\\n{2,}", chr(10), _LINE.sub("", src)).strip()
    except Exception:
        return src


def looks_like_music_request(text: str) -> bool:
    """主人是不是在让你点歌/控制音乐（避免键鼠任务循环跟点歌抢操作）"""
    try:
        t = str(text or "")
        if not t:
            return False
        kws = ("点歌", "放一首", "放首歌", "放歌", "来一首", "来首歌", "来首", "听歌",
               "放音乐", "放点音乐", "换首歌", "换一首", "换歌", "下一首", "上一首",
               "暂停音乐", "继续放", "关掉音乐", "我喜欢的音乐", "静音",
               "单曲循环", "随机播放", "列表循环", "歌词")
        return any(w in t for w in kws)
    except Exception:
        return False


# ─────────────────────── 搜索接口（只取歌名歌手） ───────────────────────

def search(query: str, limit: int = 5) -> list:
    """搜歌 → [(id, 歌名, 歌手, 专辑, fee)]

    fee 是网易云的收费标记（实测本机）：
        0 = 免费      8 = 低音质免费（不用会员也能放）
        1 = 会员专享（没会员只能试听 30 秒）   4 = 需购买专辑
    主人没会员时，优先挑 0 / 8 的结果（见 pick_best）。
    """
    try:
        import requests
        try:
            from tool.net_env import bypass_proxy_for_local
            bypass_proxy_for_local()
        except Exception:
            pass
        r = requests.get(_SEARCH_URL,
                         params={"s": str(query), "type": 1, "limit": max(1, int(limit))},
                         headers={"User-Agent": _UA, "Referer": "https://music.163.com/"},
                         timeout=(8, 15))
        data = r.json()
        songs = (((data or {}).get("result") or {}).get("songs")) or []
        out = []
        for s in songs:
            try:
                _art = "/".join(a.get("name", "") for a in (s.get("artists") or []) if a.get("name"))
                try:
                    _fee = int(s.get("fee") if s.get("fee") is not None else 0)
                except Exception:
                    _fee = 0
                out.append((int(s.get("id")), str(s.get("name") or ""), _art,
                            str((s.get("album") or {}).get("name") or ""), _fee))
            except Exception:
                continue
        return out
    except Exception as e:
        _log(f"搜索失败:{type(e).__name__}: {e}")
        return []


def _fee_label(fee: int) -> str:
    return {0: "免费", 8: "低音质免费", 1: "会员", 4: "付费专辑"}.get(int(fee or 0), "未知")


def _fee_ok(fee) -> bool:
    """这一版不用会员就能**整首放**吗？

    ★ 2026-09-24 更正：fee=8「低音质免费」是**能整首放**的（用户歌单里那首
      《蔡健雅-红色高跟鞋（DJ·less remix）》就是 fee=8，他一直听得好好的）。
      之前我按界面上那句"正在试听"判定，得出"只有 fee=0 能整首放"——那是错的
      （那句提示本身就时有时无，实测骗过好几次）。现在：0 和 8 都算能放，
      只有 1（会员）/4（付费专辑）才需要换版本。
    """
    try:
        return int(fee or 0) in (0, 8)
    except Exception:
        return True


# ─────────── 记住主人爱听哪个版本（下次优先放那一版）───────────
# 用户要求：「桌宠要记住爱听的是哪个版本的音乐，下次播放优先播放爱听的版本」。
# 存在 pets/<角色>/memory/music_prefs.json，和她的其它记忆放一起。
_pref_cache = {"path": "", "data": None}


def _pref_path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return os.path.join(d, "music_prefs.json")


def _song_key(name: str) -> str:
    """按歌名归一化做 key —— 同一首歌的各种版本要归到**同一把 key**。

    "红色高跟鞋" / "红色高跟鞋(0.88x)" / "红色高跟鞋 (Live)" / "起风了(林俊杰)"
    都算同一首歌，这样"主人爱听哪一版"才能跨版本生效（实测踩到：不带歌手点歌时，
    搜索结果第一条变成了《红色高跟鞋(0.88x)》，key 不一样就找不到记忆了）。
    括号里的版本标记（Live/remix/DJ版/0.88x…）只用来区分**版本**，不参与歌曲身份。
    """
    s = re.split(r"[（(\[【]", str(name or ""))[0]
    s = re.sub(r"[\s\-_·、,，.。!！?？~～]", "", s).lower()
    return s[:40]


def _ver_key(name: str, artist: str) -> str:
    """版本的指纹：歌名（保留括号里的标记）+ 歌手，都归一化。"""
    n = re.sub(r"[\s\-_()（）\[\]【】·、,，.。!！?？~～]", "", str(name or "")).lower()[:48]
    a = re.sub(r"[\s\-_()（）\[\]【】·、,，.。!！?？]", "", str(artist or "")).lower()[:40]
    return n + "|" + a


def _prefs() -> dict:
    p = _pref_path()
    if _pref_cache["path"] == p and _pref_cache["data"] is not None:
        return _pref_cache["data"]
    d = {}
    try:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d = json.load(f) or {}
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("songs", {})       # key(歌名) → [ {ver, artist, name, id, fee, plays, ts}, … ]
    d.setdefault("liked", {})       # ver 指纹 → {times, ts, songs:[歌名…]}
    _pref_cache["path"], _pref_cache["data"] = p, d
    return d


def _save_prefs(d: dict):
    try:
        # 只留最近 200 首歌、每首最多 6 个版本，别让文件无限长
        songs = d.get("songs") or {}
        if len(songs) > 200:
            items = sorted(songs.items(), key=lambda kv: max((x.get("ts") or 0) for x in kv[1]) if kv[1] else 0)
            d["songs"] = dict(items[-200:])
        for k, lst in list(d.get("songs", {}).items()):
            if isinstance(lst, list) and len(lst) > 6:
                d["songs"][k] = sorted(lst, key=lambda x: -(x.get("plays") or 0))[:6]
        with open(_pref_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        _pref_cache["data"] = d
    except Exception as e:
        _log(f"保存听歌偏好失败:{type(e).__name__}: {e}")


def remember_play(name: str, artist: str, song_id: int = 0, fee: int = 0) -> str:
    """记下"这一版主人听了"——同一首歌同一版本听得越多，下次越优先放它。

    只在**真的放上了**之后调用（试听/没放上不算，免得把听不了的版本记成爱听）。
    """
    try:
        nm, ar = str(name or "").strip(), str(artist or "").strip()
        if not nm:
            return ""
        d = _prefs()
        sk, vk = _song_key(nm), _ver_key(nm, ar)
        lst = d["songs"].setdefault(sk, [])
        hit = None
        for it in lst:
            if it.get("ver") == vk or (song_id and int(it.get("id") or 0) == int(song_id)):
                hit = it
                break
        if hit is None:
            hit = {"ver": vk, "name": nm, "artist": ar, "id": int(song_id or 0),
                   "fee": int(fee or 0), "plays": 0, "ts": 0.0}
            lst.append(hit)
        hit["plays"] = int(hit.get("plays") or 0) + 1
        hit["ts"] = time.time()
        hit["fee"] = int(fee or 0)
        if song_id:
            hit["id"] = int(song_id)
        liked = d["liked"].setdefault(vk, {"times": 0, "ts": 0.0, "songs": []})
        liked["times"] = int(liked.get("times") or 0) + 1
        liked["ts"] = time.time()
        if nm not in (liked.get("songs") or []):
            liked.setdefault("songs", []).append(nm)
            liked["songs"] = liked["songs"][-30:]
        _save_prefs(d)
        _log(f"记住这个版本：《{nm}》{ar}（已听 {hit['plays']} 次）")
        return f"《{nm}》{ar}"
    except Exception as e:
        _log(f"记听歌偏好出错:{type(e).__name__}: {e}")
        return ""


def preferred_for(name: str) -> dict:
    """这首歌主人爱听哪一版 → 返回**记忆里的那一条**（没有记录返回 {}）。

    ★ 为什么不去当前搜索结果里找：实测踩到过——主人第二次点同一首歌时，
      查询词略有不同（"红色高跟鞋" vs "红色高跟鞋 蔡健雅"）→ 搜索结果的 8 条里
      根本没有他爱听的那一版 → 以前就直接退回"免费优先"，放了另一个版本（用户明确不想要）。
      现在的做法是：**直接拿记忆里的歌名+歌手去搜**，那就不依赖这次搜索的结果了。
    """
    try:
        songs = _prefs().get("songs") or {}
        key = _song_key(name)
        lst = songs.get(key)
        if not lst and len(key) >= 3:
            # ★ 精确查不到就宽松匹配：记忆里存的可能是**带歌手前缀**的歌名
            #   （用户歌单里那版叫《蔡健雅-红色高跟鞋（DJ·less remix）》→ key 是
            #    "蔡健雅红色高跟鞋"），而主人点歌只会说《红色高跟鞋》→ 精确查不到。
            #   实测踩到：明明存了记忆却"下次没优先放"，就是这里对不上。
            _cands = [(k, v) for k, v in songs.items() if v and _name_loose(k, key)]
            if _cands:
                _k, lst = max(_cands, key=lambda kv: max(
                    [int(x.get("plays") or 0) for x in kv[1]] or [0]))
        if not lst:
            return {}
        best = sorted(lst, key=lambda x: (-(int(x.get("plays") or 0)), -(x.get("ts") or 0)))[0]
        if not str(best.get("name") or "").strip():
            return {}
        return {"name": str(best.get("name")), "artist": str(best.get("artist") or ""),
                "id": int(best.get("id") or 0), "fee": int(best.get("fee") or 0),
                "plays": int(best.get("plays") or 0)}
    except Exception as e:
        _log(f"查听歌偏好出错:{type(e).__name__}: {e}")
    return {}


def preferred_version(hits: list, name: str = "") -> dict:
    """（旧的"在搜索结果里找爱听版本"入口，保留兼容）→ 命中就返回 {'hit': 那一行}"""
    try:
        pf = preferred_for(name or (hits[0][1] if hits else ""))
        if not pf:
            return {}
        for h in hits or []:
            if pf.get("id") and int(h[0]) == int(pf["id"]):
                return {"hit": h, "plays": pf["plays"], "why": "id"}
        for h in hits or []:
            if _ver_key(h[1], h[2]) == _ver_key(pf["name"], pf["artist"]):
                return {"hit": h, "plays": pf["plays"], "why": "版本"}
    except Exception:
        pass
    return {}


def remember_own(name: str, artist: str = "") -> str:
    """记下"这是她自己挑的歌"（她自己的口味，和主人的收藏分开）"""
    try:
        nm = str(name or "").strip()
        if not nm:
            return ""
        d = _prefs()
        lst = d.setdefault("hers", [])
        vk = _ver_key(nm, artist)
        for it in lst:
            if it.get("ver") == vk:
                it["times"] = int(it.get("times") or 0) + 1
                it["ts"] = time.time()
                break
        else:
            lst.append({"ver": vk, "name": nm, "artist": str(artist or ""),
                        "times": 1, "ts": time.time()})
        if len(lst) > 30:
            d["hers"] = sorted(lst, key=lambda x: x.get("ts") or 0)[-30:]
        _save_prefs(d)
        _log(f"记下她自己挑的歌：《{nm}》{artist}")
        return nm
    except Exception as e:
        _log(f"记她自己挑的歌失败:{type(e).__name__}: {e}")
        return ""


def own_taste_text(limit: int = 6) -> str:
    """她自己挑过的歌（给她自己看的口味清单）"""
    try:
        lst = (_prefs().get("hers") or [])
        if not lst:
            return ""
        lst = sorted(lst, key=lambda x: -(int(x.get("times") or 0)))
        return "、".join(f"《{x.get('name')}》{x.get('artist')}" for x in lst[:limit])
    except Exception:
        return ""


def favorites_text(limit: int = 8) -> str:
    """主人常听的（给她挑歌/点歌时参考，也能直接说给主人听）"""
    try:
        d = _prefs()
        rows = []
        for sk, lst in (d.get("songs") or {}).items():
            if not lst:
                continue
            best = max(lst, key=lambda x: (int(x.get("plays") or 0), x.get("ts") or 0))
            rows.append((int(best.get("plays") or 0), best.get("ts") or 0,
                         str(best.get("name") or ""), str(best.get("artist") or "")))
        if not rows:
            return ""
        rows.sort(key=lambda x: (-x[0], -x[1]))
        return "、".join(f"《{n}》{a}（{c} 次）" for c, _t, n, a in rows[:limit])
    except Exception:
        return ""


def summary_text() -> str:
    """她记得的听歌口味（菜单/窗口里可看）"""
    fav = favorites_text(10)
    return ("主人常听的：" + fav) if fav else "（还没记住主人爱听什么）"


def _prefer_free() -> bool:
    """点歌时是否优先挑"不用会员"的版本（config 的 music_prefer_free，默认开）。

    用户要求：主人没会员时优先放不要会员的歌（不然只能听 30 秒试听）。
    """
    try:
        from tool.config import get_config
        v = str(get_config("./config.json").get("music_prefer_free", "true")).lower()
        return v not in ("false", "0", "off", "no")
    except Exception:
        return True


def _has_preview_notice(hwnd) -> bool:
    """界面上是不是出现了"正在试听…开通VIP听整首"（= 没会员，只放了 30 秒）。

    实测这句提示挂在 Group(50020) 上（'正在试听，开通黑胶VIP听整首'），
    所以按元素名扫；扫不到就返回 False（不误报）。
    """
    try:
        U = _uia()
        root = U.root_for(hwnd)
        if root is None:
            return False
        for el in U.find_all_fast(root, None, limit=1200):
            nm = U.name_of(el)
            if "试听" in nm and ("VIP" in nm or "会员" in nm or "整首" in nm):
                return True
    except Exception:
        pass
    return False


# ── 后台自动收拾弹窗（会员收银台 / 广告）──
_popup_watch = {"on": False, "last": 0.0}


def watch_popups(interval: float = 25.0):
    """起一个轻量后台线程：网易云开着时，定期自动关掉会员/广告弹窗。

    为什么放这儿（而不是让桌宠调）：桌宠的定时器都挺长（几分钟），
    会员弹窗一挡就是挡住整个播放器，得尽快关掉；这里自己盯，代价也小
    （窗口最小化时直接返回，不读控件）。
    """
    if _popup_watch["on"]:
        return
    _popup_watch["on"] = True

    def _loop():
        try:
            ctypes.windll.ole32.CoInitialize(None)     # 后台线程里用 COM 先初始化
        except Exception:
            pass
        while True:
            try:
                time.sleep(max(5.0, float(interval)))
                hwnd = find_window()
                if hwnd and not window_minimized(hwnd):
                    r = close_popups(hwnd)
                    if r:
                        print(f"[音乐] {r}")
            except Exception:
                pass

    import threading as _th
    _th.Thread(target=_loop, daemon=True, name="music-popup-watch").start()
    _log("已启动弹窗巡视（每 25 秒看一眼有没有会员/广告弹窗，有就点掉）")


def _same_song(nm: str, top: str) -> bool:
    """是不是同一首歌的版本（允许"起风了 / 周深 - 起风了 (5OC Boot"这类）"""
    a = re.sub(r"[\s\-_()（）\[\]【】·、,，.。!！?？]", "", str(nm or "")).lower()
    b = re.sub(r"[\s\-_()（）\[\]【】·、,，.。!！?？]", "", str(top or "")).lower()
    if not a or not b:
        return False
    return b in a or a in b


def pick_best(hits: list, query: str = "") -> tuple:
    """从搜索结果里挑一首最该放的。

    规则（2026-09-24 修正）：
      * 能整首放的（fee=0 免费 / 8 低音质免费）优先于要会员的（1 会员 / 4 付费）
      * 都能放时，完全免费(0) 略优（音质好些）
      * **歌手名出现在搜索词里** 的优先（避免为了一首免费去放别人的翻唱）
        —— 用户歌单里那首《蔡健雅-红色高跟鞋（DJ·less remix）》就是 fee=8，
        按老逻辑会被当成"会员曲"换掉，属于误判。
      * 一个能放的都没有 → 返回第一条（调用方会如实告诉主人要会员）
    """
    if not hits:
        return None
    try:
        top_name = str(hits[0][1] or "").strip()
        q = str(query or "")
        scored = []
        for i, h in enumerate(hits):
            try:
                _id, _nm, _art, _alb, _fee = (list(h) + [0])[:5]
                _fee = int(_fee or 0)
            except Exception:
                continue
            if not _same_song(_nm, top_name):
                continue                      # 只要同一首歌的版本
            score = 0
            if _fee_ok(_fee):
                score += 60
                if _fee == 0:
                    score += 5
            for part in re.split(r"[\s,/、·]+", str(_art or "")):
                if part and part in q:
                    score += 40
                    break
            score -= i
            scored.append((score, i, h))
        if not scored:
            return hits[0]
        scored.sort(key=lambda x: (-x[0], x[1]))
        _best = scored[0][2]
        if not _fee_ok((list(_best) + [0])[4]):
            return hits[0]                    # 一个能放的都没有 → 还是放主人点的那个
        return _best
    except Exception:
        return hits[0]


# ─────────────────────── 窗口 / 退路键鼠 ───────────────────────

def _u32():
    return ctypes.windll.user32


def find_window():
    """找网易云主窗口（没开返回 0）"""
    try:
        return int(_u32().FindWindowW(_WINDOW_CLASS, None) or 0)
    except Exception:
        return 0


def window_title(hwnd) -> str:
    """窗口标题 = 当前播放的歌（最可靠的状态来源）"""
    try:
        n = _u32().GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        _u32().GetWindowTextW(hwnd, buf, n + 2)
        return (buf.value or "").strip()
    except Exception:
        return ""


def _foreground():
    try:
        return int(_u32().GetForegroundWindow() or 0)
    except Exception:
        return 0


# ───── 最小化的窗口 UIA 读不到任何控件 → 临时还原、干完放回（不抢焦点）─────
# 实测（本机网易云 Store 版）：窗口最小化时 UIA 树里只剩窗口自己一个元素，
# 搜索框、播放按钮全读不到 → 日志里的「UIA：没找到搜索框」就是这么来的，
# 也就是说**网易云最小化时点歌必然失败**。所以动手前先悄悄还原它。
_restore_min = set()          # 我们临时还原过的窗口（干完要放回最小化）

_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010
_HWND_BOTTOM = 1


def window_minimized(hwnd) -> bool:
    try:
        return bool(_u32().IsIconic(int(hwnd)))
    except Exception:
        return False


def _uia_children(hwnd) -> int:
    """窗口 UIA 树里的元素数（最小化时是 1，正常时几百）"""
    try:
        from tool import uia as _u
        root = _u.root_for(hwnd)
        if root is None:
            return 0
        return _u.children_count(root, max_depth=3, limit=30)
    except Exception:
        return 0


def ensure_uia(hwnd) -> bool:
    """确保 UIA 能读到窗口里的控件（返回是否可用）。

    为什么需要：网易云最小化时读不到任何子控件，点歌/暂停/切歌全都会静默失败。
    做法：SW_SHOWNOACTIVATE 还原 + 压到 Z 序最底 —— **不激活、不置顶、不抢焦点**
    （你打字不会被打断），干完由 unensure_uia() 放回最小化，桌面恢复原样。
    """
    if not hwnd:
        return False
    if _uia_children(hwnd) > 1:
        return True                      # 本来就读得到（窗口没最小化）
    if not window_minimized(hwnd):
        return False                     # 不是最小化还读不到 → 真没法
    try:
        u = _u32()
        u.ShowWindow(int(hwnd), 4)       # SW_SHOWNOACTIVATE：还原但不激活
        # 压到最底层：别挡着主人正在看的窗口（已实测这样 UIA 照样能操作）
        u.SetWindowPos(int(hwnd), _HWND_BOTTOM, 0, 0, 0, 0,
                       _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOACTIVATE)
        _restore_min.add(int(hwnd))
        for _ in range(6):               # 等 UIA 树重建（通常半秒内就好）
            time.sleep(0.25)
            if _uia_children(hwnd) > 1:
                _log("网易云是最小化的 → 临时还原（没抢焦点、压在最后）才能后台操作")
                return True
        _log("还原了网易云却还是读不到控件")
        return False
    except Exception as e:
        _log(f"还原最小化窗口失败:{type(e).__name__}: {e}")
        return False


def unensure_uia(hwnd):
    """把临时还原过的窗口放回最小化（保持主人原来的桌面）"""
    try:
        h = int(hwnd or 0)
        if h and h in _restore_min:
            _restore_min.discard(h)
            _u32().ShowWindow(h, 6)      # SW_MINIMIZE
            _log("已把网易云放回最小化（保持你原来的样子）")
    except Exception:
        pass


# ─────────── 会员/广告弹窗：自动点关闭 ───────────
# 现场抓到的真实元素（2026-09-24，本机网易云点了会员歌之后）：
#   ct=50006(Image)  name='close'  rect=(1484,190,1504,210)      ← 收银台右上角的 ×
#   ct=50020(Group)  name='正在试听，开通黑胶VIP听整首'          ← 没会员时的试听提示
#   ct=50026(Slider) name='推荐 连续包月 5.5 首月 ¥18 …'         ← 收银台里的套餐
#   ct=50020(Group)  name='/st/vipcashier-v4/mini/?messageSrc=im' ← 就是会员收银台页
_POPUP_HINTS = ("会员", "VIP", "vip", "试听", "开通", "扫码", "二维码", "协议", "优惠",
                "活动", "领取", "续费", "广告", "推荐歌曲", "推广")
_CLOSE_TOKENS = ("close", "关闭", "以后再说", "稍后再说", "稍后", "跳过", "我知道了",
                 "不再提示", "暂不", "再想想", "取消", "放弃", "关掉")
# 这些词说明是"要你花钱/登录"的按钮，绝不能当关闭键点
_CLOSE_NEVER = ("开通", "立即", "领取", "续费", "购买", "支付", "试听", "登录", "同意",
                "确认", "下载", "安装", "了解更多")


def close_popups(hwnd=None, force: bool = False) -> str:
    """自动点掉网易云的会员/广告弹窗，返回干了什么（没弹窗返回空串）。

    安全设计（别乱点主人的界面）：
      ① 只有先扫到"弹窗味儿"的元素（会员/VIP/试听/开通/协议/广告…）才动手；
         force=True 时（主人明确说"关弹窗"）不看这个。
      ② 只点名字像关闭的元素（close/关闭/以后再说/稍后/跳过/我知道了/取消…），
         且**名字里带"开通/领取/续费/购买"的一律跳过**（那是让你花钱的）。
      ③ 只点有真实屏幕位置的（网易云树里有一堆 rect=(0,0,0,0) 的隐藏元素）。
    """
    try:
        if not uia_ready():
            return ""
        hwnd = int(hwnd or find_window() or 0)
        if not hwnd or window_minimized(hwnd):
            return ""                     # 最小化时读不到控件，别硬来
        U = _uia()
        root = U.root_for(hwnd)
        if root is None or U.children_count(root, max_depth=3, limit=30) <= 1:
            return ""
        popup_hint = ""
        cands = []
        # 只扫 Image / Button（实测那个 × 是 Image）——比全树快得多（0.2 秒）
        for ct in (U.CT_IMAGE, U.CT_BUTTON):
            for el in U.find_all_fast(root, ct, limit=150):
                nm = U.name_of(el).strip()
                if not nm:
                    continue
                if any(h in nm for h in _POPUP_HINTS):
                    popup_hint = popup_hint or nm[:40]
                    continue
                low = nm.lower()
                if any(t in low for t in _CLOSE_TOKENS) and not any(b in nm for b in _CLOSE_NEVER):
                    r = U.rect_of(el)
                    if r and r[2] > r[0] and r[3] > r[1] and r[2] > 0 and r[3] > 0:
                        cands.append((r[1], el, nm, r))
        if not cands:
            return ""
        if not popup_hint and not force:
            return ""                     # 没看到弹窗迹象 → 不乱按（怕关掉主人的面板）
        cands.sort(key=lambda x: x[0])
        done = []
        for _t, el, nm, r in cands[:2]:
            try:
                if U.invoke(el):
                    done.append(f"{nm}@{r}")
            except Exception:
                pass
        if done:
            _log(f"自动关掉了弹窗（{popup_hint or '手动'}）：{'、'.join(done)}")
            return (f"我把弹窗关了（{popup_hint or '按你说的'}）。" if force
                    else f"顺手关掉了一个弹窗：{popup_hint or done[0]}")
    except Exception as e:
        _log(f"关弹窗出错:{type(e).__name__}: {e}")
    return ""


def _keys(*seq):
    """发组合键/单键（退路用）"""
    from pynput.keyboard import Controller as _K, Key
    kb = _K()
    _map = {"ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift, "enter": Key.enter,
            "esc": Key.esc, "down": Key.down, "up": Key.up, "tab": Key.tab,
            "media_next": Key.media_next, "media_prev": Key.media_previous,
            "media_play": Key.media_play_pause, "space": Key.space}
    for item in seq:
        if isinstance(item, (tuple, list)):
            keys = [_map.get(str(k).lower(), str(k)) for k in item]
            for k in keys:
                kb.press(k)
            for k in reversed(keys):
                kb.release(k)
        else:
            k = _map.get(str(item).lower(), str(item))
            kb.press(k)
            kb.release(k)
        time.sleep(0.06)


def media(action: str) -> str:
    """退路：系统媒体键（只在部分网易云版本有效，Store 版实测无效）"""
    try:
        if action in ("pause", "stop"):
            _keys("media_play"); return "已经帮你暂停了。"
        if action in ("resume", "play_pause"):
            _keys("media_play"); return "给你接着放了。"
        if action == "next":
            _keys("media_next"); return "换下一首了。"
        if action == "prev":
            _keys("media_prev"); return "回到上一首了。"
    except Exception as e:
        return f"没控制上（{type(e).__name__}）。"
    return ""


def _launch_client() -> bool:
    for p in _APP_HINTS:
        try:
            if p and os.path.exists(p):
                os.startfile(p)
                time.sleep(4.0)
                return bool(find_window())
        except Exception:
            continue
    try:
        os.startfile("shell:AppsFolder")
        time.sleep(1.0)
    except Exception:
        pass
    return bool(find_window())


# ─────────────────────── UIA：后台控制 ───────────────────────

def _uia():
    from tool import uia as _u
    return _u


def uia_ready() -> bool:
    try:
        return _uia().available()
    except Exception:
        return False


def _walk_buttons(hwnd):
    """所有按钮 [(元素, 名字, 位置)]。

    ★ 用 FindAll 而不是全树 walk（实测 741 个元素的网易云：walk 0.68~1.07s，
      FindAll 0.24s）。这个函数在暂停/切歌/循环/收藏、以及桌宠每次判断
      "在不在放"时都会跑（她每隔几秒就问一次），差的就是整机的流畅度。
    """
    U = _uia()
    root = U.root_for(hwnd)
    if root is None:
        return []
    out = []
    els = U.find_all_fast(root, U.CT_BUTTON, limit=400)
    if els:
        for el in els:
            out.append((el, U.name_of(el).strip(), U.rect_of(el)))
        return out
    # 兜底：FindAll 不好使时退回全树遍历
    for el, nm, ct, _aid in U.walk(root):
        if ct == U.CT_BUTTON:
            out.append((el, str(nm).strip(), U.rect_of(el)))
    return out


def _player_button(hwnd, names):
    """在**播放条**上找按钮（play/pause/next/pre/循环/收藏/歌词/音量…）。

    ★ 必须限定在"窗口最下面那一条"：实测（2026-09-24）搜索结果页也有个名字叫
      「play 播放」的按钮（在页面中部）→ 老逻辑拿"第一个叫 play 的按钮"当基准 y，
      结果把页面中部那个播放键当成了播放条上的切换键 → 一按就换成了搜索结果里的第一首
      （用户反馈"音乐没声音，暂停再播放才有声音"那次，自动恢复播放时又按错、换了歌）。
      现在按窗口高度取底部 30% 区域（播放条在 y≈856/1080 ≈ 79%）来认。
    """
    want = [n.lower() for n in names]
    btns = _walk_buttons(hwnd)
    try:
        import ctypes
        from ctypes import wintypes as _wt
        r0 = _wt.RECT()
        ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(r0))
        top, h = int(r0.top), max(1, int(r0.bottom) - int(r0.top))
    except Exception:
        top, h = 0, 1
    _band = top + int(h * 0.70)          # 底部 30% 以内才算播放条
    _in_bar = []
    for el, nm, r in btns:
        if nm.lower() not in want or not r:
            continue
        if r[1] >= _band:
            _in_bar.append((el, nm, r))
    if _in_bar:
        _in_bar.sort(key=lambda x: x[2][1], reverse=True)   # 最靠下的那条优先
        return _in_bar[0][0], _in_bar[0][2]
    # 读不到窗口高度/位置时退回老逻辑（有按钮就先用着）
    for el, nm, r in btns:
        if nm.lower() in want:
            return el, r
    return None, None


def muted(hwnd) -> bool:
    """网易云是不是**静音**了？

    实测（2026-09-24）：那个音量键的名字会随状态变 —— 正常叫 `Volume1`、静音叫 `mute`，
    静音时界面上还有一行「音量调节 0%」。用户"放了歌却没声音"就有这一条：
    之前某个【音乐】静音 操作把它静音了，之后放的每一首都**一点声音都没有**。
    """
    try:
        for el, nm, r in _walk_buttons(hwnd):
            n = nm.strip().lower()
            if n in ("mute", "volume0"):
                return True
            if n.startswith("volume"):
                return False
        U = _uia()
        root = U.root_for(hwnd)
        if root is not None:
            for el in U.find_all_fast(root, None, limit=1200):
                if "音量调节" in str(U.name_of(el)):
                    return True
    except Exception:
        pass
    return False


def ensure_sound(hwnd) -> str:
    """静音了就点一下打开声音（返回一句说明；没静音返回空串）。

    那个音量键是**切换键**：静音时按一下恢复；正常时按一下会静音 → 所以必须先判断。
    """
    try:
        if not muted(hwnd):
            return ""
        _log("网易云是静音状态（音量 0%）→ 点一下音量键恢复声音")
        for el, nm, r in _walk_buttons(hwnd):
            if nm.strip().lower() in ("mute", "volume0"):
                if _uia().invoke(el):
                    time.sleep(0.9)
                    if muted(hwnd):
                        return "（它现在是静音的，我点了一下但好像没开成，你手动点一下小喇叭）"
                    _log("已解除静音（音量键回到正常）")
                    return "（它刚才被静音了，我已经把声音打开了）"
                break
    except Exception as e:
        _log(f"解除静音出错:{type(e).__name__}: {e}")
    return ""


def progress_moving(hwnd, seconds: float = 3.0):
    """播放进度有没有在动？True/False/None（读不到就不下结论）。

    UIA **读不到**进度（实测：播放条那个滑块既不暴露 Range/Value，子元素也不移动），
    所以用像素：抓播放条上方那一条细带两次，比指纹 —— 变了就是在走，一点没变就是卡着。
    用户反馈"播放进度条也卡着不动"就是这种卡死状态（歌载入、按钮显示在放、进度不动、
    也没声音 → 要手动暂停再播放才恢复）。
    """
    try:
        from tool import screen_capture as _sc
        import ctypes
        from ctypes import wintypes as _wt
        _r0 = _wt.RECT()
        ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(_r0))
        top, left = int(_r0.top), int(_r0.left)
        bottom, right = int(_r0.bottom), int(_r0.right)
        h = max(1, bottom - top)
        # 进度条在播放条上方那一条：取底部 22%~26% 之间的一细带，横向掐中间一段
        y0 = top + int(h * 0.86)
        y1 = top + int(h * 0.93)
        x0 = left + int((right - left) * 0.20)
        x1 = left + int((right - left) * 0.80)
        if y1 - y0 < 2 or x1 - x0 < 10:
            return None
        a = _sc.capture_qimage(0)
        if a is None:
            return None
        crop = a.copy(x0, y0, x1 - x0, y1 - y0)
        h1 = _sc.quick_hash(crop)
        time.sleep(max(0.5, float(seconds)))
        b = _sc.capture_qimage(0)
        if b is None:
            return None
        crop2 = b.copy(x0, y0, x1 - x0, y1 - y0)
        h2 = _sc.quick_hash(crop2)
        if not h1 or not h2:
            return None
        return _sc.hash_distance(h1, h2) > 0
    except Exception as e:
        _log(f"进度检测出错:{type(e).__name__}")
        return None


def _kick_playback(hwnd, force: bool = True) -> str:
    """把播放**踹通**：暂停 → 等一下 → 再播放（主人手动就是这么修的）。

    为什么默认就踹（force=True）：用户反馈"放进去了但没声音、进度条也卡着不动，
      要手动暂停再播放才有声音"。实测这台机器上网易云有这种**卡住**状态：
      歌载入了、按钮显示在放、但流没起来（静音/设备/缓冲都可能触发），
      而"暂停再播放"能重新拉一次流 —— 那就自动替他做一遍（代价不到 1 秒）。
    做完会**确保最后是"在放"**（按了没反应就再按一次，最多 3 次），
    并把结果如实说出来（弄通了 / 没弄通让他手动）。
    """
    try:
        el, nm = _play_bar_toggle(hwnd)
        if el is None:
            return ""
        _t0 = window_title(hwnd)
        was = is_playing(hwnd)
        if not force and was is not True:
            return ""
        # ① 先暂停一下（如果本来在放）
        if was is True:
            _uia().invoke(el)
            time.sleep(0.7)
            if window_title(hwnd) != _t0:
                return "（按暂停的时候歌变了，我先停手了）"
        # ② 再播放，最多按 3 次直到真的在放
        for _i in range(3):
            _uia().invoke(el)
            time.sleep(1.0)
            if window_title(hwnd) != _t0:
                return "（按播放键的时候歌变了，我先停手了）"
            if is_playing(hwnd) is True:
                if was is True:
                    _log("已暂停再播放（用户说的那种卡住，靠这个重拉播放流）→ 现在状态是在放")
                    return "（刚才它有点卡，我暂停再播放重新拉了一次）"
                return ""
        return "（它好像卡住了，我暂停再播放也没弄通——你手动点一下播放键试试）"
    except Exception as e:
        _log(f"踹播放出错:{type(e).__name__}: {e}")
        return ""


def _ensure_playing(hwnd, tries: int = 2) -> bool:
    """确保**真的在放** —— 而且**只按播放条上那一个键**，按完核对没换歌。

    ★ 2026-09-24 用户反馈"让播放的是红色高跟鞋，播放的确实是另一个音乐"，
      实测根因就在这个函数的老版本：它把页面上**所有**叫 play/pause 的元素
      排成一列挨个按（包括页面中部那个），结果
        · 第一个把正在放的歌**暂停**了；
        · 第二个**把别的歌放了起来**（标题真的从《些许遗憾…》变成《红色高跟鞋（DJ版）》）。
      现在：
        ① 只认播放条（窗口最下面那一条）上的那一个键；
        ② 按之前记下标题，按完**核对标题没变**——变了立刻停手、不冒充放上了；
        ③ 读不到播放条键就**什么都不按**（宁可不动，也不能把主人的歌换掉）。
    """
    try:
        if is_playing(hwnd) is True:
            return True
        el, nm = _play_bar_toggle(hwnd)
        if el is None:
            _log("播放条上找不到播放/暂停键 → 不敢乱按（怕按到别的歌），这次先不动")
            return False
        _t0 = window_title(hwnd)
        for _i in range(max(1, int(tries))):
            if is_playing(hwnd) is True:
                return True
            try:
                if not _uia().invoke(el):
                    break
            except Exception:
                break
            time.sleep(1.0)
            if window_title(hwnd) != _t0:
                _log("按了播放键之后歌变了 → 立刻停手（不冒充放上了）")
                return False
            if is_playing(hwnd) is True:
                _log(f"按了播放条上的键（{nm}）→ 真的响起来了")
                return True
        return is_playing(hwnd) is True
    except Exception as e:
        _log(f"恢复播放出错:{type(e).__name__}: {e}")
        return False


def _invoke_player(hwnd, names) -> bool:
    U = _uia()
    el, _r = _player_button(hwnd, names)
    if el is None:
        return False
    ok = U.invoke(el)
    if ok:
        _log(f"后台按下播放条按钮「{names[0]}」（窗口没动）")
    return bool(ok)


def current_loop_mode(hwnd) -> str:
    """当前循环方式（singleloop / loop / shuffle / order），读不到返回空"""
    for _el, nm, _r in _walk_buttons(hwnd):
        if nm.lower() in _LOOP_MODES:
            return nm.lower()
    return ""


def set_loop_mode(hwnd, want: str) -> str:
    """把循环方式按到想要的那个（按钮是循环切换的，最多按 4 次）"""
    if not uia_ready():
        return ""
    try:
        cur = current_loop_mode(hwnd)
        if cur == want:
            return _LOOP_MODES[want]
        for _ in range(4):
            if not _invoke_player(hwnd, list(_LOOP_MODES.keys())):
                break
            time.sleep(0.7)
            cur = current_loop_mode(hwnd)
            if cur == want:
                _log(f"循环方式已设为 {_LOOP_MODES[cur]}")
                return _LOOP_MODES[want]
        return _LOOP_MODES.get(cur, "")
    except Exception as e:
        _log(f"设置循环方式失败:{e}")
        return ""


def progress_value(hwnd) -> float:
    """播放进度（滑块数值）—— 用它判断到底在不在放"""
    try:
        U = _uia()
        from comtypes.gen import UIAutomationClient as UIA
        root = U.root_for(hwnd)
        if root is None:
            return -1.0
        for el, nm, ct, _aid in U.walk(root):
            if ct != U.CT_SLIDER or "播放进度" not in str(nm):
                continue
            # 滑块要用 RangeValuePattern 读（Chromium 的 slider 不提供 ValuePattern）
            try:
                pat = el.GetCurrentPattern(UIA.UIA_RangeValuePatternId)
                if pat is not None:
                    rv = pat.QueryInterface(UIA.IUIAutomationRangeValuePattern)
                    return float(rv.CurrentValue)
            except Exception:
                pass
            try:
                pat = el.GetCurrentPattern(UIA.UIA_ValuePatternId)
                if pat is not None:
                    vp = pat.QueryInterface(UIA.IUIAutomationValuePattern)
                    m = re.search("-?\\d+(?:\\.\\d+)?", str(vp.CurrentValue))
                    if m:
                        return float(m.group(0))
            except Exception:
                pass
    except Exception:
        pass
    return -1.0


def _play_bar_toggle(hwnd):
    """播放条（窗口**最下面那一条**）上的播放/暂停键 → (元素, 名字)；找不到 (None, '')。

    ★ 2026-09-24 实测（这次的关键）：同一个页面里存在**好几个**叫 play/pause 的元素：
        播放条上那个（y≈754，窗口底部）    ← 正确的，只会切播放/暂停
        页面中部另一个（y≈508/551）        ← 按一下**会把别的歌放起来**！
        rect=(0,0,0,0) 的隐藏几个          ← 有的能切、有的会换歌，不可靠
      以前 is_playing() 读的是"第一个叫 play/pause 的" → 很可能读到**中部那个**
      → 状态判断飘忽、自动恢复播放按到错误按钮（把用户点的歌换成别的歌、
      或者把正在放的音乐暂停）。所以判断和按键都**只认播放条这一个**。
    """
    try:
        import ctypes
        from ctypes import wintypes as _wt
        _r0 = _wt.RECT()
        ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(_r0))
        _band = int(_r0.top) + int(max(1, int(_r0.bottom) - int(_r0.top)) * 0.72)
    except Exception:
        _band = None
    best = None
    for el, nm, r in _walk_buttons(hwnd):
        if nm.lower() not in ("play", "pause"):
            continue
        if not r or r[2] <= r[0] or r[3] <= r[1]:
            continue                      # 隐藏元素（rect 全 0）不要
        if _band is not None and r[1] < _band:
            continue                      # 不在底部那一条 → 不是播放条上的
        if best is None or r[1] > best[2][1]:   # 取最靠下的那个（播放条在最底下）
            best = (el, nm, r)
    return (best[0], best[1]) if best else (None, "")


def is_playing(hwnd):
    """在不在播放：True（在放）/ False（暂停着）/ **None（读不到，不知道）**。

    只读**播放条上那一个**切换键的名字（实测：暂停时叫 play、在放时叫 pause）——
    页面中部还有一个同名元素，读它会得到完全相反的答案（见 _play_bar_toggle）。
    读不到 → None：让调用方别乱猜（宁可不说，也不要按错按钮把歌换掉）。
    """
    el, nm = _play_bar_toggle(hwnd)
    if el is not None:
        return nm.lower() == "pause"
    btns = _walk_buttons(hwnd)
    if not btns:
        return None                      # 一个控件都读不到 → 最小化/没开/还在加载
    a = progress_value(hwnd)
    if a < 0:
        return None
    time.sleep(1.2)
    b = progress_value(hwnd)
    return b > a and b >= 0


def _clean_sidebar_name(raw: str) -> str:
    """侧边栏元素的 name 常带内部标识（例："sidebar_like 我喜欢的音乐 side"）→ 只留人话"""
    s = str(raw or "").strip()
    if "我喜欢的音乐" in s:
        return "我喜欢的音乐"
    s = re.sub(r"^sidebar_[A-Za-z0-9_]*\s*", "", s)
    s = re.sub(r"\s*side(down|up)?\s*$", "", s)
    s = re.sub(r"\s*(slide_up|slide_down)\s*", " ", s)
    return s.strip()


def list_playlists() -> list:
    """侧边栏里能看到的歌单名（含「我喜欢的音乐」）——给她挑歌用"""
    try:
        now = time.time()
        if _playlists_cache["v"] and now - float(_playlists_cache["t"] or 0) < _PLAYLIST_TTL:
            return list(_playlists_cache["v"])
        if not uia_ready():
            return []
        hwnd = find_window()
        if not hwnd:
            return []
        U = _uia()
        root = U.root_for(hwnd)
        if root is None:
            return []
        out = []
        for el, nm, ct, aid in U.walk(root):
            r = U.rect_of(el)
            if not r:
                continue
            # 侧边栏：窗口左侧一条，宽度像条目
            if r[0] < 610 and 30 <= (r[2] - r[0]) <= 200 and (r[3] - r[1]) >= 12:
                s = _clean_sidebar_name(str(nm))
                if s and s not in out and len(s) <= 22:
                    out.append(s)
        _playlists_cache["t"], _playlists_cache["v"] = now, out
        return out
    except Exception:
        return []


def _click_nav_item(hwnd, name: str) -> bool:
    """打开侧边栏里的条目（我喜欢的音乐 / 某个歌单）——UIA invoke，后台"""
    try:
        U = _uia()
        root = U.root_for(hwnd)
        if root is None:
            return False
        if name and ("我喜欢" in name):
            for el, nm, ct, aid in U.walk(root):
                if str(aid) == "left_nav_myFav" or "我喜欢的音乐" in str(nm):
                    if U.invoke(el):
                        _log("后台打开「我喜欢的音乐」（窗口没动）")
                        time.sleep(1.1)
                        return True
        for el, nm, ct, aid in U.walk(root):
            if name and name in str(nm):
                r = U.rect_of(el)
                if not r or r[0] > 610:
                    continue
                if U.invoke(el):
                    _log(f"后台打开歌单「{nm}」（窗口没动）")
                    time.sleep(1.1)
                    return True
    except Exception as e:
        _log(f"打开歌单失败:{e}")
    return False


def play_play_all(hwnd) -> bool:
    """按歌单页上的「播放全部」"""
    try:
        U = _uia()
        root = U.root_for(hwnd)
        if root is None:
            return False
        for el, nm, ct, aid in U.walk(root):
            if ct == U.CT_BUTTON and "播放全部" in str(nm):
                if U.invoke(el):
                    _log("后台按下「播放全部」（窗口没动）")
                    time.sleep(1.3)
                    return True
    except Exception:
        pass
    return False


# ─────────────────────── 后台点歌 ───────────────────────

def _uia_play(name: str, artist: str, _skip_preview_check: bool = False) -> str:
    """后台点歌（UIA）。

    返回：
        'ok'                点上了、而且能完整放（不是会员试听）
        'preview:<歌名>'    点上了，但界面上出现"正在试听，开通黑胶VIP听整首"
                            （= 这首要会员，只放了 30 秒）
        'other:<歌名>'      点上了但不是这首
        'fail' / ''         没成 / UIA 不可用
    """
    try:
        U = _uia()
        if not U.available():
            return ""
        hwnd = find_window()
        if not hwnd:
            return ""
        root = U.root_for(hwnd)
        if root is None:
            return ""
        _before = window_title(hwnd)
        box = U.top_bar_edit(root, hwnd)
        if box is None:
            _log("UIA：没找到搜索框")
            return "fail"
        if not U.set_value(box, f"{name} {artist}".strip()):
            _log("UIA：写不进搜索框")
            return "fail"
        _log("UIA：已把歌名写进搜索框（窗口没切到前台）")
        # ── 找搜索按钮：轮询 + 按位置兜底 ──
        # 为什么不能只找一次：窗口刚从最小化还原时 UIA 树是**逐步长出来**的，
        # 而这个 search 按钮在整棵树里排得很靠后（实测第 656/741 个）→
        # 树没长全就找不着 → 以前直接报"没找到 search 按钮"放弃（用户看到的就是点了没反应）。
        box_rect = U.rect_of(box)
        btn = None
        for _try in range(6):                        # 最多等 1.5 秒
            hit = U.buttons_named(root, contains="search", limit=400)
            if hit:
                btn = hit[0][0]
                break
            alt, _ar = U.button_next_to(root, box_rect)
            if alt is not None:
                btn = alt
                _log("UIA：按位置认出搜索按钮（名字没匹配上）")
                break
            time.sleep(0.25)
            root = U.root_for(hwnd) or root
        if btn is None:
            _log("UIA：没找到 search 按钮（等了 1.5 秒）")
            return "fail"
        U.invoke(btn)
        _log("UIA：已提交搜索")
        # ── ① 先确认"结果页真的出了这首歌" ──
        #    为什么：搜索没生效时页面还停着上一次的结果，直接点第一个「播放」
        #    就会放出一首你没点的歌（2026-09-23 实测踩到：想放《夜空中最亮的星》，
        #    结果放了《起风了》）。所以宁可不点，也不放错。
        got = False
        cands = []
        for _try in range(14):
            time.sleep(0.4)
            r2 = U.root_for(hwnd)
            # 用 FindAll 取按钮（实测 0.24s，walk 要 0.7~1.1s）——这一轮最多要跑 14 次，
            # 差的就是好几秒（用户感觉到的"慢"）
            for el, s, r in U.buttons_named(r2, contains="播放", limit=400):
                if "全部" in s:
                    continue
                if r:
                    cands.append((r[1], el, s, r))
            if not got:
                # 结果页里有没有这首歌。★ 必须查**所有**元素类型：网易云把歌名挂在
                # Group(50020) 上（不是 Text）——只查 Text 会误判"没搜到"，
                # 于是明明搜出来了也不敢点（2026-09-24 实测踩到）。
                # 比对用**宽松匹配**（带版本后缀的歌名 vs 行名只写歌名，见 _name_loose）。
                # FindAll(全部) 实测 0.10s，比 walk 快得多，随便查。
                els = U.find_all_fast(r2, None, limit=1200)
                if not els:
                    els = [e for e, _n, _c, _a in U.walk(r2, limit=800)]
                for el in els:
                    _nm2 = U.name_of(el)
                    if _name_hit(_nm2, name) or _name_loose(_nm2, name):
                        got = True
                        break
            if got and cands:
                if _try:
                    _log(f"UIA：等了 {(_try + 1) * 0.4:.1f} 秒，结果页出来了")
                break
        if not cands:
            _log("UIA：结果页没找到「播放」按钮")
            return "fail"
        if not got:
            _log(f"UIA：结果页没出现「{name}」→ 不点播放（否则会放出旧结果里的歌）")
            return "fail"
        cands.sort(key=lambda x: x[0])
        _log(f"UIA：按第一条结果的按钮「{cands[0][2][:20]}」{cands[0][3]}")
        if not U.invoke(cands[0][1]):
            return "fail"
        # 等它真的开始放（轮询标题，最多 3 秒；以前死等 1.5 秒）
        _hit = False
        for _ in range(10):
            time.sleep(0.3)
            if _title_hit(window_title(hwnd), name):
                _hit = True
                break
        if not _hit:
            for _r, _el, _nm, _rc in cands[1:4]:
                U.invoke(_el)
                for _ in range(6):
                    time.sleep(0.3)
                    if _title_hit(window_title(hwnd), name):
                        _hit = True
                        break
                if _hit:
                    break
        if _hit and not _skip_preview_check:
            # ★ 光"标题对上了"还不够：实测（2026-09-24 用户反馈）点搜索结果里的播放键
            #   有时只是把歌**载入**播放器，播放器自己还是暂停状态 → 标题变了、我们以为
            #   放上了，实际**一点声音都没有**，要手动暂停再播放才响（用户的原话）。
            #   这里再确认一次"真的在放"，没在放就自己按一下那个播放/暂停切换键。
            try:
                # ★ 先查静音：实测（2026-09-24）网易云自己会被静音（音量 0%、键名叫 mute），
                #   这时候"放进去了、按钮显示在放"，但**一点声音都没有**（用户反馈）。
                _note(ensure_sound(hwnd))
                if is_playing(hwnd) is False:
                    _log("标题对上了但播放器是暂停状态 → 自己想办法让它响")
                    if not _ensure_playing(hwnd):
                        _log("（试了播放条上的切换键，还是没放起来——读不到状态就不硬说）")
                # ★ 再踹一下卡死的情况：按钮说在放、进度却一动不动、也没声音
                #   （用户反馈"播放进度条也卡着不动"）→ 暂停再播放，就是主人手动那一套
                _note(_kick_playback(hwnd))
            except Exception as _e2:
                _log(f"确认播放状态出错:{type(_e2).__name__}")
            # 顺手看一眼界面上的"正在试听…"——但**不作为唯一判据**：实测它可能一闪而过
            # （网易云切歌瞬间会短暂出现），所以调用方会再确认一次才当数。
            try:
                if _has_preview_notice(hwnd):
                    return "preview:" + str(window_title(hwnd) or name)
            except Exception:
                pass
            return "ok"
        if _hit:
            return "ok"
        # 没对上日志：把实际标题打出来，方便排查"明明点了却没认出来"
        _log(f"点了但没认出来：标题={str(window_title(hwnd))[:40]!r}｜要找的是《{name}》")
        # ② 歌换了但不是要的那首 → 如实说，不冒充成功
        _now = window_title(hwnd)
        if _now and _now != _before:
            _log(f"点上了，但放的不是《{name}》，而是《{_now}》")
            return "other:" + str(_now)
        return "fail"
    except Exception as e:
        _log(f"UIA 点歌出错: {type(e).__name__}: {e}")
        return ""


def _name_hit(text: str, name: str) -> bool:
    """结果页里出现这首歌了吗（歌名或其前 4 个字命中）"""
    s = str(text or "")
    n = str(name or "").strip()
    if not s or not n:
        return False
    if n in s:
        return True
    key = n[:4]
    return len(key) >= 3 and key in s


def _name_loose(text: str, name: str) -> bool:
    """宽松匹配：只比"歌曲本体"，忽略括号里的版本标记、前后缀和**词序**。

    为什么要它（2026-09-24 两次实测踩到）：
      ① 主人点名的是带版本的名字《蔡健雅-红色高跟鞋（DJ·less remix）》，
         客户端结果页的行名只写《红色高跟鞋》→ 严格比对判成"没搜到"，搜到了也不点；
      ② 网易云的标题写《红色高跟鞋 - 蔡健雅》，我点名的是《蔡健雅-红色高跟鞋…》
         → 歌名/歌手顺序相反，"包含"也不成立 → 误判"没放上"，然后去换版本
         （正是用户不想要的）。
    现在：去掉括号里的标记、去标点空格 → 一边包含另一边，或**有 4 个字重叠**就算同一首。
    """
    a, b = _song_key(text), _song_key(name)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    for i in range(max(0, len(short) - 3)):
        if short[i:i + 4] in long:
            return True
    return False


def _title_hit(title: str, name: str) -> bool:
    """窗口标题里出现歌名（或歌名前几个字）就算点上了。

    带版本后缀点名时（《蔡健雅-红色高跟鞋（DJ·less remix）》）标题只会写
    《红色高跟鞋 - 蔡健雅》，所以这里也要走宽松匹配（只比歌曲本体）。
    """
    t = str(title or "")
    n = str(name or "").strip()
    if not t or not n:
        return False
    if n in t:
        return True
    key = n[:4]
    if bool(key) and key in t:
        return True
    return _name_loose(t, n)


def play_song(query: str) -> str:
    """搜索 + 播放一首歌（后台 UIA；UIA 不可用时退回媒体键并如实说明）"""
    q = _norm(query)
    if not q:
        return "你没说歌名呀。"
    if _busy[0]:
        _log("已经在操作音乐了 → 这次请求先不重复执行")
        return "我正在给你弄呢，等一下下。"
    try:
        _now = time.time()
        _hist = [t for t in (_attempts.get(q) or []) if _now - t < _ATTEMPT_WINDOW]
        _last = max(_hist) if _hist else 0
        # ★ 冷却策略（2026-09-24 改）：以前是"5 分钟内只许试 2 次"，一旦失败两次，
        #   主人再喊也只会被挡回去，而她还在反复承诺"这回真给你放" —— 用户看到的就是
        #   "点歌卡住了"。现在改成：两次尝试之间至少隔 _ATTEMPT_GAP 秒，
        #   10 分钟内最多 _ATTEMPT_LIMIT 次。既能防住疯狂连点，又不用主人干等 5 分钟。
        if _last and (_now - _last) < _ATTEMPT_GAP:
            _log(f"「{q}」{_ATTEMPT_GAP:.0f} 秒内刚试过 → 先等一下再试")
            return "唔……这个我刚刚按过，你等一两秒我再试一次。"
        if len(_hist) >= _ATTEMPT_LIMIT:
            _log(f"「{q}」{_ATTEMPT_WINDOW // 60} 分钟内已试过 {len(_hist)} 次 → 先不重复")
            return (f"《{q}》我试了好几次都没放上，先不硬试了——"
                    f"你自己点一下播放键更快，或者过一会儿再喊我。")
        _hist.append(_now)
        _attempts[q] = _hist
    except Exception:
        pass
    _busy[0] = True
    _hwnd0 = 0
    try:
        watch_popups()          # 顺手把"弹窗巡视"挂上：会员/广告弹窗一出现就被点掉
        hits = search(q, limit=8)
        if not hits:
            return f"搜不到「{q}」这首歌，换个写法试试？"
        _pick = pick_best(hits, q) if _prefer_free() else hits[0]
        _sid, name, artist, _alb, _fee = (list(_pick) + [0])[:5]
        try:
            _fee = int(_fee or 0)
        except Exception:
            _fee = 0
        _log(f"搜到：《{name}》{artist}（id={_sid}，{_fee_label(_fee)}）"
             + (f"｜候选 {len(hits)} 首，挑了免费的版本" if _pick is not hits[0] else ""))
        # 依次尝试的顺序（2026-09-24 修正版）：
        #   ① **主人爱听的那一版**（music_prefs.json 里记着，直接按它的歌名+歌手去搜）
        #   ② **主人点名的那一版** —— 只要它自己不用会员（fee=0/8）就直接放它，
        #      **不替换**（用户歌单里那首《蔡健雅-红色高跟鞋（DJ·less remix）》是 fee=8，
        #      能整首放；老逻辑会把它换成"完全免费"的翻唱版 → 属于误判/多此一举）
        #   ③ 只有当点名那版**真的能不放**（fee=1/4 会员/付费）时，才去找能放的替代版本
        # 客户端只能放"搜索结果第一条"，所以换版本的办法是**换成那个版本的搜索词**再搜一次。
        _pref = preferred_for(name) if _prefer_free() else {}
        _tries, _seen = [], set()
        if _pref.get("name"):
            _tries.append((_pref["name"], _pref["artist"],
                           f"你爱听的版本·听过 {_pref.get('plays') or 1} 次 ",
                           int(_pref.get("fee") or 0)))
            _seen.add(_ver_key(_pref["name"], _pref["artist"]))
            _log(f"主人爱听的是：《{_pref['name']}》{_pref['artist']}"
                 f"（听过 {_pref.get('plays') or 1} 次）→ 优先放这一版")
        _ask_fee = None
        try:
            _ask_hit = next((h for h in hits
                             if _ver_key(h[1], h[2]) == _ver_key(name, artist)), None)
            _ask_fee = int((_ask_hit or hits[0])[4] or 0)
        except Exception:
            _ask_fee = 0
        if _fee_ok(_ask_fee) and _ver_key(name, artist) not in _seen:
            _tries.append((name, artist, "", _ask_fee))     # 点名那版能放 → 直接放它
            _seen.add(_ver_key(name, artist))
        if _prefer_free() and not _fee_ok(_ask_fee):
            try:                                      # 点名那版要会员 → 找能放的替代
                for h in hits:
                    if not _fee_ok(h[4]):
                        continue
                    if not _same_song(h[1], name):
                        continue
                    if _ver_key(h[1], h[2]) in _seen:
                        continue
                    _tries.append((str(h[1]), str(h[2]),
                                   "免费版本 " if int(h[4] or 0) == 0 else "低音质免费版本 ",
                                   int(h[4] or 0)))
                    _seen.add(_ver_key(h[1], h[2]))
            except Exception:
                pass
        if _ver_key(name, artist) not in _seen:
            _tries.append((name, artist, "", _ask_fee))
            _seen.add(_ver_key(name, artist))
        if _prefer_free():
            try:
                for h in hits:
                    if int(h[4] or 0) != 0:                       # 只有完全免费的才值得换
                        continue
                    if not _same_song(h[1], name):
                        continue
                    if str(h[1]).strip() == str(name).strip() and str(h[2]).strip() == str(artist).strip():
                        continue
                    _tries.append((str(h[1]), str(h[2]), "免费版本 "))
            except Exception:
                pass
        try:
            _tries = _tries[:3]
        except Exception:
            pass
        hwnd = find_window()
        if not hwnd:
            _log("客户端没开 → 尝试拉起")
            if not _launch_client():
                return "网易云没开着，你先打开它我再帮你点。"
            hwnd = find_window()
        if not hwnd:
            return "我没找到网易云的窗口。"
        _hwnd0 = hwnd
        _prev_fg = _foreground()
        # 最小化时 UIA 读不到控件 → 先悄悄还原（不抢焦点），点完再放回去
        if not ensure_uia(hwnd):
            return (f"我搜到了《{name}》{artist}，但网易云这会儿读不到界面"
                    f"（大概刚最小化/正在加载）——你把它点开一下，我再给你放。")
        _u, _preview, _label = "", False, ""
        for _i, _try in enumerate(_tries):
            _n2, _a2, _lab = str(_try[0]), str(_try[1]), str(_try[2])
            _this_fee = int(_try[3] if len(_try) > 3 else 0) or 0
            if _i:
                _log(f"上一版没成 → 换成「{_n2} {_a2}」再搜一次")
            _u = _uia_play(_n2, _a2)
            if _u == "ok" or str(_u).startswith("preview:"):
                # ★ 歌确实换成了「这一版」——名字和它自己的 fee 都跟着走
                #   （以前靠"名字+歌手"回查，同名同歌手的不同版本会撞上原版的 fee：
                #    换成 fee=8 的版本后，回查却拿到原版的 fee=1，于是又误报"这首是会员曲"）
                name, artist, _label = _n2, _a2, _lab
                _fee = _this_fee
                if _u == "ok":
                    break
                # ★ 界面上那句"正在试听"实测**不稳定**（同一首能放的歌这次有、下次没有）：
                #   只要这一版自己**能整首放**（fee=0 免费 / 8 低音质免费），就不要因为
                #   这句话把它换掉 —— 否则"主人爱听的那一版"会被误换成别的版本
                #   （用户明确反馈：我歌单里那首 remix 是 fee=8、能放，却被当成会员曲换掉了）。
                if _fee_ok(_this_fee):
                    _preview = False
                    _log(f"（界面提示'试听'，但这一版是{_fee_label(_this_fee)}、能整首放 → 不换版本）")
                    break
                _preview = True
                continue
            _preview = False
            break                              # 其他结果（other/fail）不用再换版本了
        _played = _u == "ok" or str(_u).startswith("preview:")
        # 点完顺手收拾弹窗：没会员时点会员歌 → 网易云会弹"开通黑胶VIP"的收银台
        _cleaned = ""
        try:
            _cleaned = close_popups(hwnd)
        except Exception:
            pass
        # 到底是不是"只能试听"？
        # ★ 界面上那句"正在试听，开通黑胶VIP听整首"**不稳定**（能整首放的歌也会冒出来），
        #   所以只对"本来就放不了"的版本（fee=1 会员 / 4 付费）采信，而且会**连查两次**；
        #   能整首放的版本（fee=0 免费 / 8 低音质免费）一律不信它，不让它掀翻判断。
        if _played and not _label and not _fee_ok(_fee):
            try:
                if _has_preview_notice(hwnd):
                    time.sleep(1.8)
                    if _has_preview_notice(hwnd):
                        _preview = True
            except Exception:
                pass
        _tag = f"（{_label}）" if _label else ""
        _vip_only = not _fee_ok(_fee)          # 最终那版要会员(fee=1/4) → 才提示
        # ★ 界面上的"正在试听"提示**不稳定**（同一首歌这次有、下次没有，实测），
        #   所以不让它推翻确定的判断：fee=0 的歌一律按"放上了"报，
        #   只有 fee≠0 的会员/付费曲才提示"可能要会员、只能试听"。
        if _played and (not _preview or not _vip_only):
            try:      # 网易云开始播放时会自己跳到前台一次 → 再把焦点还给主人
                if _prev_fg and _prev_fg != int(hwnd):
                    _restore_foreground(_prev_fg)
            except Exception:
                pass
            if _vip_only:
                try:
                    remember_play(name, artist, _sid, _fee)
                except Exception:
                    pass
                return (f"给你放上了：《{name}》{artist}{_tag}。"
                        f"（这首是{_fee_label(_fee)}曲，没会员的话可能只能试听 30 秒——"
                        f"我已经优先找过免费版本，这首没有。）{take_notes()}")
            # ★ 记住"主人听了这一版"——下次点同一首歌就先放它（用户要求）
            try:
                _sid2 = 0
                for _h in hits:
                    if str(_h[1]).strip() == str(name).strip() and str(_h[2]).strip() == str(artist).strip():
                        _sid2 = int(_h[0])
                        break
                remember_play(name, artist, _sid2 or _sid, _fee)
            except Exception:
                pass
            return f"给你放上了：《{name}》{artist}{_tag}。{take_notes()}"
        if _preview:
            try:
                if _prev_fg and _prev_fg != int(hwnd):
                    _restore_foreground(_prev_fg)
            except Exception:
                pass
            _extra = ("我把能整首放的免费版本都试过了，都没成。"
                      if len(_tries) > 1 else "这首在网易云上没有能整首放的免费版本。")
            return (f"《{name}》{artist}**只能放 30 秒试听**（这首要黑胶会员）。"
                    f"{_extra}如实告诉主人：要么开会员，要么换一首别的歌。")
        if str(_u).startswith("other:"):
            _wrong = str(_u).split(":", 1)[1]
            try:
                if _prev_fg and _prev_fg != int(hwnd):
                    _restore_foreground(_prev_fg)
            except Exception:
                pass
            return (f"我点上了，但放出来的是《{_wrong}》，不是你要的《{name}》——"
                    f"可能网易云那边的搜索结果不太对，你手动挑一下，或者换个写法喊我。")
        if not uia_ready():
            return media("play_pause") or f"我搜到了《{name}》{artist}，但没法后台播放。"
        return (f"我搜到了《{name}》{artist}，但没能替你按上播放。"
                + (f"（{_cleaned}）" if _cleaned else "")
                + "别自己重复点歌了：如实跟主人说「没点上、你手动按一下播放」，"
                  "或者等主人再喊你一次。")
    finally:
        _busy[0] = False
        unensure_uia(_hwnd0 or find_window())


# ─────────────────────── 状态与统一入口 ───────────────────────

def _version_hint(hwnd, name: str, artist: str) -> str:
    """在界面上找"这首歌的真实版本名"（含 remix/DJ版/Live 等标记）。

    为什么要它：窗口标题只有「歌名 - 歌手」，光看这个去 API 里查，查到的往往是
    **另一版**（用户歌单里那首是《蔡健雅-红色高跟鞋（DJ·less remix）》，按标题查却
    查到要 VIP 的《红色高跟鞋》原版 → 误判成会员曲）。
    歌单/列表里的行名带完整版本信息（实测行名形如
    "05 蔡健雅-红色高跟鞋（DJ·less remix） jymaster DJ·"），拿它当线索最准。
    """
    try:
        U = _uia()
        root = U.root_for(hwnd)
        if root is None:
            return ""
        key = _song_key(name)
        for el in U.find_all_fast(root, None, limit=1500):
            nm = str(U.name_of(el) or "")
            if not nm or key and key not in _song_key(nm):
                continue
            if "(" not in nm and "（" not in nm and "remix" not in nm.lower() and "版" not in nm:
                continue                       # 行名里没有版本标记 → 不是我们要的线索
            if artist and artist not in nm:
                continue
            return nm[:60]
    except Exception:
        pass
    return ""


def _fee_of_version(name: str, artist: str, hint: str = "") -> int:
    """查"这一版"的收费标记（-1 = 查不到）。

    先用歌名+歌手+hint（行名里的版本标记）搜；能精确对上歌手/版本名的那条才采信。
    """
    try:
        _hint = re.sub(r"^\s*\d+\s*", "", str(hint or "")).strip()
        _hint = re.sub(r"\s+\S+\.\S+.*$", "", _hint)      # 去掉行名尾巴上的专辑/歌手串
        q = f"{name} {artist} {_hint}".strip()
        hits = search(q, limit=8)
        if not hits and _hint:
            hits = search(f"{_hint}".strip(), limit=8)
        if not hits:
            return -1
        _seen = [h for h in hits if _same_song(h[1], name)]
        if not _seen:
            return -1
        for h in _seen:                        # 版本名对得上（含括号里的标记）→ 最可信
            if _hint and re.sub(r"\s", "", _hint).lower()[:18] in re.sub(r"\s", "", h[1]).lower():
                return int(h[4] or 0)
        for h in _seen:                        # 歌手对得上
            if artist and (artist in str(h[2]) or str(h[2]) in artist):
                return int(h[4] or 0)
        return int(_seen[0][4] or 0)
    except Exception:
        return -1


def fix_vip_now_playing(auto_switch: bool = False) -> str:
    """现在放的这首是不是"只能试听"的会员曲？**如实报一句**（拿不准就不说）。

    为什么需要（2026-09-24 用户反馈）：「我喜欢的音乐」里存的那一版是要 VIP 的，
    整单开始播就是会员曲（只能试听 30 秒）→ 她说"给你放了"，主人听到的却是试听。
    ⚠ 但更要紧的是**别乱说**：用户明确指出"我歌单里的红色高跟鞋并不是要 VIP 的那个原版"——
      之前按窗口标题「歌名 - 歌手」去 API 里查，查到的是**同名另一版**（要 VIP 的原版），
      于是把他那首 fee=8（低音质免费、能整首放）的 remix 误判成会员曲。
    现在的做法：先拿界面上**歌单行里的完整版本名**当线索，查**那一版**的 fee；
    查不到 / 对不上 / fee=0 或 8（能放） → 一律**闭嘴**，不打扰主人。
    """
    try:
        if not uia_ready():
            return ""
        hwnd = find_window()
        if not hwnd:
            return ""
        title = str(window_title(hwnd) or "").strip()
        if not title or " - " not in title:
            return ""
        name, artist = re.split(r"\s+-\s+", title, 1)
        name, artist = name.strip(), artist.strip()
        # ① 主人爱听的那一版是不是就是它？（记忆里记着他听的那版的 fee）
        pf = preferred_for(name)
        if pf and pf.get("name") and (
                (pf.get("artist") and artist
                 and (artist in str(pf["artist"]) or str(pf["artist"]) in artist))):
            _pff = int(pf.get("fee") or 0)
            if _fee_ok(_pff):
                _log(f"现在放的是主人爱听的版本《{name}》{pf.get('artist')}（{_fee_label(_pff)}）")
                return ""                  # 能整首放 → 不用说什么
        # ② 看界面上这首歌的真实版本名（歌单行）→ 查那一版的 fee
        hint = _version_hint(hwnd, name, artist)
        _fee = _fee_of_version(name, artist, hint)
        _log(f"核对版本：《{name}》{artist}"
             + (f"｜行名线索 {hint[:28]!r}" if hint else "（界面上没有版本线索）")
             + f"｜查到 {_fee_label(_fee) if _fee >= 0 else '查不到'}")
        if _fee < 0 or _fee_ok(_fee):
            return ""                      # 查不到或能整首放 → 闭嘴（宁可不提，也别误判）
        hits = search(f"{name} {artist}".strip(), limit=8)
        _free = next((h for h in hits
                      if _fee_ok(h[4]) and _same_song(h[1], name)), None)
        if _free is not None and auto_switch:
            _log(f"这首《{name}》是要会员的 → 换成能放的《{_free[1]}》{_free[2]}")
            _r = play_song(f"{_free[1]} {_free[2]}")
            return f"（不过《{name}》是要会员的，只能试听；我给你换了能放的版本《{_free[1]}》{_free[2]}。{str(_r)[:40]}）"
        if _free is not None:
            return (f"（不过这首《{name}》是{_fee_label(_fee)}曲、只能试听 30 秒；"
                    f"想听整首就跟我说「放 {_free[1]} {_free[2]}」。）")
        return f"（不过这首《{name}》是{_fee_label(_fee)}曲，没会员只能听 30 秒试听——网上没有能整首放的版本。）"
    except Exception as e:
        _log(f"歌单会员曲处理出错:{type(e).__name__}: {e}")
        return ""


def status_text() -> str:
    """现在放的是什么、在不在放、循环方式（读不到就如实说读不到，不瞎猜）"""
    hwnd = find_window()
    if not hwnd:
        return "网易云没开着。"
    t = window_title(hwnd) or "（不知道）"
    pl = is_playing(hwnd)
    if pl is None:
        _log("读不到播放状态（网易云最小化着？）→ 只报歌名")
        return f"现在放的是《{t}》（最小化着我读不到在不在放）"
    state = "在放" if pl else "没在放（或已暂停）"
    mode = current_loop_mode(hwnd)
    return f"现在{state}：《{t}》" + (f"，循环方式{_LOOP_MODES.get(mode, mode)}" if mode else "")


def run(text: str) -> str:
    """执行她写的【音乐】标记，返回一句结果说明（没有标记返回空串）"""
    acts = parse(text)
    if not acts:
        return ""
    kind, arg = acts[0]
    _fg_before = _foreground()
    _hwnd_before = find_window()
    try:
        _r = _run_locked(kind, arg)
    except Exception as e:
        _log(f"执行{kind} 失败: {type(e).__name__}: {e}")
        _r = f"我这边操作音乐出了点问题（{type(e).__name__}）。"
    # ★ 网易云有时会自己跳到前台（开始/切换播放时）→ 把前台还给主人原来的窗口
    try:
        _h = find_window()
        if _fg_before and _h and _fg_before != int(_h) and _foreground() == int(_h):
            _restore_foreground(_fg_before)
    except Exception:
        pass
    # ★ 为了操作而临时还原的最小化窗口 → 放回最小化（保持主人原来的桌面）
    unensure_uia(_hwnd_before or find_window())
    return _r


def _restore_foreground(prev_fg: int) -> bool:
    """把前台/焦点还给主人原来的窗口。

    网易云一开始播放就会自己跳到最前面（它客户端的行为），不还回去会打断主人打字。
    直接 SetForegroundWindow 常被前台锁挡住 → 补一次"模拟按一下 Alt"
    （系统会认为用户刚操作过，前台锁松一格，这是标准做法；比 AttachThreadInput 安全）。
    """
    try:
        u = _u32()
        u.SetForegroundWindow(int(prev_fg))
        time.sleep(0.12)
        if _foreground() == int(prev_fg):
            _log("已把前台还给主人原来的窗口")
            return True
        try:
            from pynput.keyboard import Controller as _K, Key
            kb = _K()
            kb.press(Key.alt)
            time.sleep(0.04)
            kb.release(Key.alt)
            time.sleep(0.08)
            u.SetForegroundWindow(int(prev_fg))
            time.sleep(0.15)
        except Exception:
            pass
        ok = _foreground() == int(prev_fg)
        _log("已把前台还给主人原来的窗口" if ok else "（网易云抢着当前台，没能还回去）")
        return ok
    except Exception:
        return False


def _run_locked(kind: str, arg: str) -> str:
    """（上面的 run() 负责兜异常 + 还原前台，真正干活的在这里）"""
    try:
        if kind == "play":
            return play_song(arg)
        if kind == "search":
            hits = search(arg, limit=5)
            if not hits:
                return f"搜不到「{arg}」。"
            return "搜到这些：" + "；".join(
                f"《{n}》{a}（{_fee_label(f)}）" for _i, n, a, _al, f in hits)
        if kind == "mine":
            if arg:
                _a = str(arg).strip()                 # ⚠ 参数前面带空格，先 strip 再拆（否则歌名是空串）
                r = play_song(_a)
                try:
                    _parts = _a.split(" ")
                    remember_own(_parts[0], " ".join(_parts[1:]))
                except Exception:
                    pass
                return "这首是我自己想听的：" + str(r)
            mine = (_prefs().get("hers") or [])
            if not mine:
                return ("我还没自己挑过歌呢——你让我「放你想听的」，我就挑一首我喜欢的。"
                        "（也可以直接说歌名，我记着。）")
            mine = sorted(mine, key=lambda x: -(x.get("ts") or 0))
            pick = mine[0]
            r = play_song(f"{pick.get('name')} {pick.get('artist')}".strip())
            return f"我想听这首：《{pick.get('name')}》（我自己挑的）。{r}"
        if kind == "favorites":
            fav = favorites_text(8)
            return ("主人常听的是：" + fav) if fav else "我还没记住主人爱听什么——你多点几次，我就记住了。"
        if kind == "close_popup":
            hwnd = find_window()
            if not hwnd:
                return "网易云没开着。"
            if window_minimized(hwnd) and not ensure_uia(hwnd):
                return "网易云最小化着，我读不到它的界面。"
            r = close_popups(hwnd, force=True)
            return r or "我看了看，没有弹窗。"
        if kind == "now":
            return status_text()
        hwnd = find_window()
        if not hwnd:
            return "网易云没开着，你打开它我再帮你。"
        if not uia_ready():
            mp = {"pause": "pause", "resume": "resume", "next": "next", "prev": "prev",
                  "play_pause": "play_pause"}
            if kind in mp:
                return media(mp[kind])
            return "这台机器上后台控制不可用（没装 comtypes），我只能用系统媒体键。"
        # 最小化时 UIA 读不到控件 → 先悄悄还原（不抢焦点），run() 结束时放回去
        if not ensure_uia(hwnd):
            return "网易云这会儿读不到界面（最小化着或者刚在加载），你先点开它一下。"
        # ── 播放控制（全部后台，不切窗口）──
        if kind in ("pause", "resume", "play_pause"):
            cur_playing = is_playing(hwnd)
            if kind == "pause" and cur_playing is False:
                return "现在就是暂停着的。"
            if kind == "resume" and cur_playing is True:
                return "本来就在放着呢。"
            # ★ 那个按钮是**切换键**：在放的时候它叫 pause、暂停时叫 play。
            #   以前只找 "play" → 正在播放时找不到按钮，暂停就静默失败了
            #   （还会谎报"给你接着放了"）。这里两个名字都认。
            if not _ensure_playing(hwnd):
                _log("没能让它放起来（播放条上的切换键都试过了）")
                return "我按了播放条，但它好像没反应——你手动按一下吧。"
            time.sleep(0.6)
            now_playing = is_playing(hwnd)
            if now_playing is None:
                return "我按了一下播放条，但读不到状态——你听一下有没有响。"
            if kind == "pause":
                return "给你暂停了。" if now_playing is False else "按了暂停，但好像还在放——你再喊我一次。"
            if kind == "resume":
                return "给你接着放了。" if now_playing is True else "按了播放，但好像没响——你再喊我一次。"
            return "给你暂停了。" if now_playing is False else "给你接着放了。"
        if kind == "next":
            _invoke_player(hwnd, ["next"])
            time.sleep(1.3)
            return f"换下一首了：《{window_title(hwnd)}》。"
        if kind == "prev":
            _invoke_player(hwnd, ["pre"])
            time.sleep(1.3)
            return f"回到上一首：《{window_title(hwnd)}》。"
        if kind in ("loop_single", "loop_list", "loop_random", "loop_order"):
            want = {"loop_single": "singleloop", "loop_list": "loop",
                    "loop_random": "shuffle", "loop_order": "order"}[kind]
            m = set_loop_mode(hwnd, want)
            return f"设成{m}了。" if m else "循环方式没改成。"
        if kind == "liked":
            if _click_nav_item(hwnd, "我喜欢的音乐"):
                if play_play_all(hwnd):
                    time.sleep(1.2)
                    _note = fix_vip_now_playing()      # 歌单里那首是会员曲？换成免费版
                    return "给你放上「我喜欢的音乐」了。" + _note
                return "打开了「我喜欢的音乐」，但没找到播放按钮。"
            return "没找到「我喜欢的音乐」入口。"
        if kind == "playlist":
            if not arg:
                pls = list_playlists()
                return ("你的歌单有：" + "、".join(pls[:8])) if pls else "侧边栏没看到歌单。"
            for nm in list_playlists():
                if arg in str(nm) or str(nm) in arg:
                    if _click_nav_item(hwnd, str(nm)) and play_play_all(hwnd):
                        time.sleep(1.2)
                        return f"切到歌单「{nm}」放上了。" + fix_vip_now_playing()
            if _click_nav_item(hwnd, arg) and play_play_all(hwnd):
                time.sleep(1.2)
                return f"切到歌单「{arg}」放上了。" + fix_vip_now_playing()
            return f"没找到叫「{arg}」的歌单。"
        if kind == "favorite":
            _invoke_player(hwnd, ["collect"])
            return "给你收藏了这首。"
        if kind == "lyric":
            _invoke_player(hwnd, ["lyric"])
            return "把歌词界面打开了。"
        if kind == "mute":
            _invoke_player(hwnd, ["Volume1"])
            return "切换了静音。"
    except Exception as e:
        _log(f"执行{kind} 失败: {type(e).__name__}: {e}")
        return f"我这边操作音乐出了点问题（{type(e).__name__}）。"
    return ""


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=== 解析 ===")
    for t in ("【音乐】暂停", "【音乐】下一首", "【音乐】单曲循环", "【音乐】随机播放",
              "【音乐】我喜欢", "【音乐】播放歌单 火影忍者上分bgm", "【音乐】在放什么",
              "【音乐】播放 沦陷 dj", "【音乐】收藏", "【音乐】歌词"):
        print("  %-30s → %s" % (t, parse(t)))
    print()
    print("UIA 可用:", uia_ready())
    h = find_window()
    print("窗口:", h, "| 标题:", window_title(h))
    print("在放:", is_playing(h), "| 循环方式:", current_loop_mode(h))
    print("歌单:", list_playlists()[:10])
    print("状态:", status_text())
