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
# 每首歌的尝试时间戳：短时间内试太多次就不再试，免得"一直重复搜索"
_attempts = {}
_ATTEMPT_WINDOW = 300
_ATTEMPT_LIMIT = 2
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
    """交给模型的能力说明（自动带上主人的歌单，方便她自己挑）"""
    pls = list_playlists()
    pl_line = ""
    if pls:
        pl_line = "主人的歌单（可以自己挑着放）：" + "、".join(pls[:8]) + "。\n"
    return (
        "【音乐控制（网易云，已开启）】你可以自己操作网易云音乐，在回复里单独写一行：\n"
        "【音乐】播放 歌名 歌手（例如【音乐】播放 沦陷 dj）\n"
        "【音乐】暂停 / 继续 / 下一首 / 上一首\n"
        "【音乐】单曲循环 / 列表循环 / 随机播放 / 顺序播放\n"
        "【音乐】我喜欢（直接放「我喜欢的音乐」）／【音乐】播放歌单 名字\n"
        "【音乐】收藏 / 歌词 / 静音 / 在放什么\n"
        + pl_line +
        "★ 这些都是**后台执行**：不切走主人的画面、不动鼠标，放心用。\n"
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
    """搜歌 → [(id, 歌名, 歌手, 专辑)]"""
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
                out.append((int(s.get("id")), str(s.get("name") or ""), _art,
                            str((s.get("album") or {}).get("name") or "")))
            except Exception:
                continue
        return out
    except Exception as e:
        _log(f"⚠ 搜索失败: {type(e).__name__}: {e}")
        return []


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
        _log("⚠ 还原了网易云却还是读不到控件")
        return False
    except Exception as e:
        _log(f"⚠ 还原最小化窗口失败: {type(e).__name__}: {e}")
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
    U = _uia()
    root = U.root_for(hwnd)
    if root is None:
        return []
    out = []
    for el, nm, ct, aid in U.walk(root):
        if ct == U.CT_BUTTON:
            r = U.rect_of(el)
            out.append((el, str(nm).strip(), r))
    return out


def _player_button(hwnd, names):
    """在播放条区域找按钮（按 name 匹配 + 用 y 坐标限定在播放条那一条上）"""
    want = [n.lower() for n in names]
    btns = _walk_buttons(hwnd)
    y_ref = None
    for _el, nm, r in btns:
        if nm.lower() == "play" and r:
            y_ref = r[1]
            break
    for el, nm, r in btns:
        if nm.lower() in want:
            if y_ref is None or not r or abs(r[1] - y_ref) <= 60:
                return el, r
    return None, None


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
        _log(f"⚠ 设置循环方式失败: {e}")
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


def is_playing(hwnd):
    """在不在播放：True（在放）/ False（暂停着）/ **None（读不到，不知道）**。

    实测：播放条上那个按钮的 name 会随状态变（暂停时是 play、播放时是 pause），
    比读进度滑块可靠得多（那个元素经常读不到或已经失效）。
    ★ 关键：网易云**最小化**时整个 UIA 树是空的 → 这时绝不能断言"没在放"
    （否则她会以为没歌、又去点一首）。读不到就返回 None，让调用方别乱猜。
    """
    btns = _walk_buttons(hwnd)
    for _el, nm, _r in btns:
        n = nm.lower()
        if n == "pause":
            return True
        if n == "play":
            return False
    if not btns:
        return None                      # 一个控件都读不到 → 最小化/没开/还在加载
    # 有控件但没找到播放按钮 → 退回进度判断
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
        _log(f"⚠ 打开歌单失败: {e}")
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

def _uia_play(name: str, artist: str) -> str:
    """后台点歌（UIA）：'ok' 成功 / 'other:<歌名>' 点上了但不是这首 / 'fail' 没成 / '' 不可用"""
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
        btn = U.find(root, control_type=U.CT_BUTTON, contains="search")
        if btn is not None:
            U.invoke(btn)
            _log("UIA：已提交搜索")
        else:
            _log("UIA：没找到 search 按钮（不按了，免得放出旧结果）")
            return "fail"
        # ── ① 先确认"结果页真的出了这首歌" ──
        #    为什么：搜索没生效时页面还停着上一次的结果，直接点第一个「播放」
        #    就会放出一首你没点的歌（2026-09-23 实测踩到：想放《夜空中最亮的星》，
        #    结果放了《起风了》）。所以宁可不点，也不放错。
        got = False
        cands = []
        for _try in range(14):
            time.sleep(0.5)
            cands = []
            for el, nm, ct, aid in U.walk(U.root_for(hwnd)):
                s = str(nm)
                if ct == U.CT_BUTTON and "播放" in s and "全部" not in s:
                    r = U.rect_of(el)
                    if r:
                        cands.append((r[1], el, s, r))
                elif _name_hit(s, name):
                    got = True
            if got and cands:
                if _try:
                    _log(f"UIA：等了 {(_try + 1) * 0.5:.1f} 秒，结果页出来了")
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
        time.sleep(1.5)
        if _title_hit(window_title(hwnd), name):
            return "ok"
        for _r, _el, _nm, _rc in cands[1:4]:
            U.invoke(_el)
            time.sleep(1.3)
            if _title_hit(window_title(hwnd), name):
                return "ok"
        # ② 歌换了但不是要的那首 → 如实说，不冒充成功
        _now = window_title(hwnd)
        if _now and _now != _before:
            _log(f"⚠ 点上了，但放的不是《{name}》，而是《{_now}》")
            return "other:" + str(_now)
        return "fail"
    except Exception as e:
        _log(f"UIA 点歌出错: {type(e).__name__}: {e}")
        return ""


def _name_hit(text: str, name: str) -> bool:
    """结果页里出现这首歌了吗（歌名或其前 4 个字命中；排除界面本身的"搜索"字样）"""
    s = str(text or "")
    n = str(name or "").strip()
    if not s or not n:
        return False
    if n in s:
        return True
    key = n[:4]
    return len(key) >= 3 and key in s


def _title_hit(title: str, name: str) -> bool:
    """窗口标题里出现歌名（或歌名前几个字）就算点上了"""
    t = str(title or "")
    n = str(name or "").strip()
    if not t or not n:
        return False
    if n in t:
        return True
    key = n[:4]
    return bool(key) and key in t


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
        if len(_hist) >= _ATTEMPT_LIMIT:
            _log(f"「{q}」{_ATTEMPT_WINDOW // 60} 分钟内已试过 {len(_hist)} 次 → 不再重复")
            return (f"《{q}》我刚试过两次都没放上，先不重复了——"
                    f"你再喊我一次我再试，或者你自己点一下播放键。")
        _hist.append(_now)
        _attempts[q] = _hist
    except Exception:
        pass
    _busy[0] = True
    _hwnd0 = 0
    try:
        hits = search(q, limit=5)
        if not hits:
            return f"搜不到「{q}」这首歌，换个写法试试？"
        _sid, name, artist, _alb = hits[0]
        _log(f"搜到：《{name}》{artist}（id={_sid}）")
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
        _u = _uia_play(name, artist)
        if _u == "ok":
            _log(f"✅ 播放成功（后台 UIA）：{window_title(hwnd)}")
            try:      # 网易云开始播放时会自己跳到前台一次 → 再把焦点还给主人
                if _prev_fg and _prev_fg != int(hwnd):
                    _restore_foreground(_prev_fg)
            except Exception:
                pass
            return f"给你放上了：《{name}》{artist}。"
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
                f"别自己重复点歌了：如实跟主人说「没点上、你手动按一下播放」，"
                f"或者等主人再喊你一次。")
    finally:
        _busy[0] = False
        unensure_uia(_hwnd0 or find_window())


# ─────────────────────── 状态与统一入口 ───────────────────────

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
        _log(f"⚠ 执行 {kind} 失败: {type(e).__name__}: {e}")
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
            hits = search(arg, limit=3)
            if not hits:
                return f"搜不到「{arg}」。"
            return "搜到这些：" + "；".join(f"《{n}》{a}" for _i, n, a, _al in hits)
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
            if not _invoke_player(hwnd, ["play", "pause"]):
                _log("⚠ 没找到播放/暂停按钮")
                return "我没找到播放条上那个按钮——你手动按一下吧。"
            time.sleep(1.0)
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
                    return "给你放上「我喜欢的音乐」了。"
                return "打开了「我喜欢的音乐」，但没找到播放按钮。"
            return "没找到「我喜欢的音乐」入口。"
        if kind == "playlist":
            if not arg:
                pls = list_playlists()
                return ("你的歌单有：" + "、".join(pls[:8])) if pls else "侧边栏没看到歌单。"
            for nm in list_playlists():
                if arg in str(nm) or str(nm) in arg:
                    if _click_nav_item(hwnd, str(nm)) and play_play_all(hwnd):
                        return f"切到歌单「{nm}」放上了。"
            if _click_nav_item(hwnd, arg) and play_play_all(hwnd):
                return f"切到歌单「{arg}」放上了。"
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
        _log(f"⚠ 执行 {kind} 失败: {type(e).__name__}: {e}")
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
