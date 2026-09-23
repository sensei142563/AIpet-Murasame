# -*- coding: utf-8 -*-
"""点歌：让她真的去网易云搜索并播放。

为什么这么做（现场勘查这台机器的结论）：
    * 网易云在运行（进程 cloudmusic），窗口类名 `OrpheusBrowserHost`，
      **窗口标题就是当前播放的歌**（例如"烟袋斜街 - 接个吻，开一枪/SaMZIng"）
      → 这就是最可靠的"成功校验点"。
    * `orpheus://song/<id>` 协议**没有注册**（Store 版没写注册表），本地 API 端口
      （27232/27233）也没开 → 没法用官方协议/接口点播。
    * 搜索接口可用：https://music.163.com/api/search/get 返回真实结果。
    所以：**HTTP 搜索拿到歌名歌手 → 驱动客户端界面搜索 → 播放 → 用窗口标题验证**
    （标题里出现歌名/关键词就算点上了；没变就再试，最后如实说没成）。

标记（她说，桌宠执行）：
    【音乐】播放 沦陷 dj        ← 点播（搜索 + 播放）
    【音乐】暂停 / 继续 / 下一首 / 上一首 / 停止
"""
import ctypes
import os
import re
import time

MUSIC_MARK = "【音乐】"
_WINDOW_CLASS = "OrpheusBrowserHost"     # 网易云客户端主窗口
_SEARCH_URL = "https://music.163.com/api/search/get"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
_APP_HINTS = (
    os.path.expandvars(r"%ProgramFiles(x86)%\NetEase\CloudMusic\cloudmusic.exe"),
    os.path.expandvars(r"%ProgramFiles%\NetEase\CloudMusic\cloudmusic.exe"),
    os.path.expandvars(r"%LocalAppData%\NetEase\CloudMusic\cloudmusic.exe"),
)

_LINE = re.compile("[【\\[]\\s*音乐\\s*[】\\]]\\s*([^\"\\]\\n]{1,80})")

# 同一个播放请求同时只能跑一个（她自己会连着催；两个自动化抢鼠标键盘谁都点不成）
_busy = [False]
# 每首歌的尝试时间戳：短时间内试太多次就不试了，免得"一直重复搜索"
_attempts = {}
_ATTEMPT_WINDOW = 300      # 5 分钟内
_ATTEMPT_LIMIT = 2         # 同一首歌最多试 2 次


def _log(msg: str):
    try:
        print(f"[音乐] {msg}")
    except Exception:
        pass


# 主人这句话是不是在"点歌/控制音乐"（自然语言判断，parse() 只看标记，不够用）
_MUSIC_WORDS = ("点歌", "放一首", "放首歌", "放歌", "来一首", "来首歌", "来首", "听歌",
                "放音乐", "放点音乐", "换首歌", "换一首", "下一首", "上一首",
                "暂停音乐", "继续放", "别放歌", "关掉音乐")


def looks_like_music_request(text: str) -> bool:
    """主人是不是在让你点歌/控制音乐（用来避免键鼠任务循环跟点歌抢操作）"""
    try:
        t = str(text or "")
        if not t:
            return False
        return any(w in t for w in _MUSIC_WORDS)
    except Exception:
        return False


def prompt_rules() -> str:
    """交给模型的能力说明"""
    return (
        "【点歌 / 控制音乐（已开启）】你可以真的操作网易云音乐，在回复里单独写一行：\n"
        "【音乐】播放 歌名 歌手（例如【音乐】播放 沦陷 dj）——桌宠会去搜索并播放它\n"
        "【音乐】暂停 / 【音乐】继续 / 【音乐】下一首 / 【音乐】上一首\n"
        "★ 主人说「帮我点歌」「放一首…」「来首…」时就用这个，不要自己去点搜索框猜坐标。\n"
        "★ 一次只点一首；点完用你自己的话跟他说放的是哪首（桌宠会把真正的歌名告诉你）。\n"
        "★ 用这个的时候**不要再写【键鼠】指令**：桌宠点歌时会自己操作搜索框和回车，"
        "你再动手就会两边抢鼠标，结果谁都点不成（实测就是这么失败的）。\n"
        "★ 如果桌宠告诉你「没放上 / 没能确认播放」，**不要自己重复点歌**（重复请求会被拒绝）："
        "如实跟主人说没点上、让他手动按一下播放键，或者等他再喊你一次。\n"
        "★ 标记那一行不会念出来，也不会显示给主人看。"
    )


# ─────────────────────── 解析 / 清理 ───────────────────────

def _norm(s: str) -> str:
    return re.sub("\\s+", " ", str(s or "")).strip()


def parse(text: str) -> list:
    """解析出要做的音乐动作：[(动作, 参数)]"""
    out = []
    for m in _LINE.finditer(str(text or "")):
        s = _norm(m.group(1)).strip("：:，,。")
        if not s:
            continue
        low = s.lower()
        if any(k in s for k in ("暂停", "停一下", "pause")):
            out.append(("pause", ""))
        elif any(k in s for k in ("继续", "播放吧", "接着", "resume", "play_pause")):
            out.append(("resume", ""))
        elif any(k in s for k in ("下一首", "下首", "下一曲", "next")):
            out.append(("next", ""))
        elif any(k in s for k in ("上一首", "上首", "上一曲", "prev")):
            out.append(("prev", ""))
        elif any(k in s for k in ("停止", "关掉音乐", "stop")):
            out.append(("stop", ""))
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
        out = _LINE.sub("", src).strip()
        out = re.sub("\\n{2,}", chr(10), out)
        return out.strip()
    except Exception:
        return src


# ─────────────────────── 搜索 ───────────────────────

def search(query: str, limit: int = 5) -> list:
    """搜歌 → [(id, 歌名, 歌手, 专辑)]"""
    try:
        import requests
        from tool.net_env import bypass_proxy_for_local
        try:
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
                _alb = ((s.get("album") or {}).get("name") or "")
                out.append((int(s.get("id")), str(s.get("name") or ""), _art, _alb))
            except Exception:
                continue
        return out
    except Exception as e:
        _log(f"⚠ 搜索失败: {type(e).__name__}: {e}")
        return []


# ─────────────────────── Windows 窗口 / 键盘 / 剪贴板 ───────────────────────

def _u32():
    return ctypes.windll.user32


def find_window():
    """找网易云主窗口（没开返回 0）"""
    try:
        h = _u32().FindWindowW(_WINDOW_CLASS, None)
        return int(h or 0)
    except Exception:
        return 0


def window_title(hwnd) -> str:
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


def _focus(hwnd) -> bool:
    """把客户端窗口带到前台（成功返回 True）

    ⚠ 这里**只用最朴素的做法**：ShowWindow + SetForegroundWindow。
      曾经加过 AttachThreadInput 那种"绕前台锁"的写法，实测不但抢不到焦点，
      还可能把调用线程和别人的输入队列挂在一起、在驱动/游戏全屏时卡住（
      桌宠主线程就是这样被拖成"未响应"的），已经删掉。
    """
    try:
        u = _u32()
        SW_RESTORE = 9
        u.ShowWindow(hwnd, SW_RESTORE)
        u.SetForegroundWindow(hwnd)
        time.sleep(0.25)
        return _foreground() == int(hwnd)
    except Exception:
        return False


def _set_clipboard(text: str) -> bool:
    """把文字放进剪贴板（这样中文也能"打"进搜索框）"""
    try:
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        # ⚠ 64 位下必须声明返回类型：GlobalAlloc/GlobalLock 返回的是指针大小的句柄，
        #   默认按 c_int 处理会被截断成 0 → 后面 memmove 到空指针（access violation）。
        k32.GlobalAlloc.restype = ctypes.c_void_p
        k32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        u32.SetClipboardData.restype = ctypes.c_void_p
        u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        data = str(text)
        if not u32.OpenClipboard(None):
            _log("⚠ OpenClipboard 失败（别的程序占着剪贴板？）")
            return False
        try:
            u32.EmptyClipboard()
            size = (len(data) + 1) * ctypes.sizeof(ctypes.c_wchar)
            h = k32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not h:
                return False
            p = k32.GlobalLock(h)
            if not p:
                _log("⚠ GlobalLock 返回空")
                return False
            buf = ctypes.create_unicode_buffer(data)
            ctypes.memmove(ctypes.c_void_p(p), buf, size)
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(CF_UNICODETEXT, h):
                return False
            return True
        finally:
            u32.CloseClipboard()
    except Exception as e:
        _log(f"⚠ 写剪贴板失败: {e}")
        return False


def _keys(*seq):
    """按顺序发送组合键/单键：('ctrl','f') 或 ('enter',) 或 ('media_next',)"""
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
    """播放控制：用系统媒体键（网易云认这些键，稳定不依赖界面）"""
    try:
        if action == "pause" or action == "stop":
            _keys("media_play")            # 播放/暂停 是同一个键
            return "已经帮你暂停了。"
        if action == "resume" or action == "play_pause":
            _keys("media_play")
            return "给你接着放了。"
        if action == "next":
            _keys("media_next")
            return "换下一首了。"
        if action == "prev":
            _keys("media_prev")
            return "回到上一首了。"
    except Exception as e:
        return f"没控制上（{type(e).__name__}）。"
    return ""


# ─────────────────────── 点播 ───────────────────────

def _launch_client() -> bool:
    """网易云没开就试着拉起来"""
    for p in _APP_HINTS:
        try:
            if p and os.path.exists(p):
                os.startfile(p)
                time.sleep(4.0)
                return bool(find_window())
        except Exception:
            continue
    try:                                   # Store 版：从开始菜单找
        os.startfile("shell:AppsFolder")
        time.sleep(1.0)
    except Exception:
        pass
    return bool(find_window())


def _win_rect(hwnd):
    """窗口的屏幕矩形 (left, top, right, bottom)"""
    try:
        import ctypes as _c
        r = _c.wintypes.RECT()
        _u32().GetWindowRect(hwnd, _c.byref(r))
        return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except Exception:
        return 0, 0, 0, 0


def _click(x: int, y: int):
    """真实鼠标点击（点击本身就会把焦点给那个窗口，不依赖前台锁）"""
    try:
        u = _u32()
        u.SetCursorPos(int(x), int(y))
        time.sleep(0.12)
        u.mouse_event(0x0002, 0, 0, 0, 0)      # LEFT DOWN
        time.sleep(0.05)
        u.mouse_event(0x0004, 0, 0, 0, 0)      # LEFT UP
        time.sleep(0.2)
    except Exception as e:
        _log(f"⚠ 点击失败: {e}")


def _search_box_candidates(hwnd) -> list:
    """搜索框可能的几个位置（相对窗口：网易云的搜索框在顶部偏左/居中）

    实测拿不到它内部控件（CEF 界面不暴露无障碍元素），所以给几个候选点位挨个试，
    用"窗口标题是否变成这首歌"来判定成功。都是顶部条区域，点错了也只是切换页面，安全。
    """
    l, t, r, b = _win_rect(hwnd)
    w = max(1, r - l)
    out = []
    for fx in (0.33, 0.45, 0.55, 0.25):
        out.append((int(l + w * fx), int(t + 22)))
    return out


def play_song(query: str, dry_run: bool = False) -> str:
    """搜索 + 播放一首歌；返回一句给主人听的结果说明。

    dry_run=True 时只做到"搜进搜索框"，不按最后那下回车（不会真的换歌，测试用）。
    """
    q = _norm(query)
    if not q:
        return "你没说歌名呀。"
    # 同一个东西同时在跑 → 别再起一个（两个自动化抢鼠标键盘，谁都点不成）
    if _busy[0]:
        _log("已经在点歌了 → 这次请求先不重复执行")
        return "我正在给你弄呢，等一下下。"
    # 同一首歌短时间内试太多次就别试了（"一直重复搜索"就是这么来的）
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
    try:
        return _play_song_locked(q)
    finally:
        _busy[0] = False


def _play_song_locked(q: str, dry_run: bool = False) -> str:
    hits = search(q, limit=5)
    if not hits:
        return f"搜不到「{q}」这首歌，换个写法试试？"
    sid, name, artist, _alb = hits[0]
    _log(f"搜到：《{name}》{artist}（id={sid}）")

    hwnd = find_window()
    if not hwnd:
        _log("客户端没开 → 尝试拉起")
        if not _launch_client():
            return "网易云没开着，你先打开它我再帮你点。"
        hwnd = find_window()
    if not hwnd:
        return "我没找到网易云的窗口。"

    # ⚠ 主人正在打全屏游戏时**不要去抢焦点**：
    #   点歌要先把网易云切到最前面再敲键盘，这会把游戏切出去（画面一黑/掉帧），
    #   而且实测这种情况下最容易把桌宠主线程卡住（"未响应"）。宁可不做。
    try:
        from tool.perf_guard import game_mode
        if game_mode():
            _log("检测到全屏游戏 → 不抢焦点，等主人打完")
            return (f"你在打游戏，我不抢你的画面啦。等这局完了跟我说一声，"
                    f"我马上给你放《{name}》。")
    except Exception:
        pass

    before = window_title(hwnd)
    prev_fg = _foreground()
    ok = False
    try:
        _focus(hwnd)                        # 顺手试一下（失败也没关系，下面靠点击拿焦点）
        keyword = f"{name} {artist}".strip()
        for i, (bx, by) in enumerate(_search_box_candidates(hwnd), 1):
            _log(f"试第 {i} 个搜索框位置 ({bx},{by})")
            _click(bx, by)                  # 点搜索框：既定位光标也把窗口带到前面
            if not _set_clipboard(keyword):
                return "剪贴板打不开，没法帮你打歌名。"
            _keys(("ctrl", "a"))            # 清掉搜索框里已有的字
            _keys(("ctrl", "v"))            # 粘贴歌名（中文只能靠剪贴板）
            time.sleep(0.35)
            _keys("enter")                  # 搜索
            time.sleep(1.6)
            if dry_run:
                _keys("esc")
                time.sleep(0.3)
                _log("（演练：只搜不播）")
                return f"（演练）搜到了《{name}》{artist}，没有真的播放。"
            _keys("enter")                  # 播放第一条结果
            time.sleep(1.3)
            if _title_hit(window_title(hwnd), name):
                ok = True
                break
            _keys("down")                   # 有的版本要 ↓ 选中第一条再回车
            _keys("enter")
            time.sleep(1.4)
            if _title_hit(window_title(hwnd), name):
                ok = True
                break
    finally:
        try:                                # 把鼠标/前台还给主人
            if prev_fg and prev_fg != int(hwnd):
                _u32().SetForegroundWindow(prev_fg)
        except Exception:
            pass

    if ok:
        _log(f"✅ 播放成功：{window_title(hwnd)}")
        return f"给你放上了：《{name}》{artist}。"
    _log(f"⚠ 没能确认播放（标题：{window_title(hwnd) or '空'}，点之前是「{before}」）")
    return (f"我搜到了《{name}》{artist}，但没能替你按上播放。"
            f"别自己重复点歌了：直接跟主人说「没点上、你手动按一下播放」，"
            f"或者等主人再喊你一次。")


def _title_hit(title: str, name: str) -> bool:
    """窗口标题里出现歌名（或歌名的前几个字）就算点上了"""
    t = str(title or "")
    n = str(name or "").strip()
    if not t or not n:
        return False
    if n in t:
        return True
    # 标题里可能只有一部分（长歌名被截断）→ 用前 4 个字比对
    key = n[:4]
    return bool(key) and key in t


def run(text: str) -> str:
    """执行她写的【音乐】标记，返回一句结果说明（没有标记返回空串）"""
    acts = parse(text)
    if not acts:
        return ""
    kind, arg = acts[0]
    if kind == "play":
        return play_song(arg)
    if kind == "search":
        hits = search(arg, limit=3)
        if not hits:
            return f"搜不到「{arg}」。"
        return "搜到这些：" + "；".join(f"《{n}》{a}" for _i, n, a, _al in hits)
    return media(kind)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=== 解析 ===")
    for t in ("【音乐】播放 沦陷 dj", "【音乐】暂停", "【音乐】下一首",
              "好，我给你放。【音乐】播放 起风了 周深"):
        print("  %-30s → %s" % (t, parse(t)))
    print()
    print("=== 搜索（真网络）===")
    for _id, n, a, al in search("沦陷 dj", limit=3):
        print("  %s | %s | %s" % (_id, n, a))
    print()
    print("=== 窗口 ===")
    h = find_window()
    print("  hwnd =", h, "| 当前播放:", window_title(h) or "（没开）")
