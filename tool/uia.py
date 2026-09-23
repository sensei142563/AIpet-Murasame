# -*- coding: utf-8 -*-
"""UI Automation（UIA）后台操作：**不切窗口、不抢焦点、不动鼠标**地操作其它程序。

为什么需要（主人要求）：
    "后台窗口执行不显示窗口进行执行任务" —— 模拟键鼠必须先把目标窗口切到最前面，
    而 UIA 可以直接给控件设值（ValuePattern）或按按钮（InvokePattern），
    目标窗口全程待在后台。网易云是 CEF 界面：MSAA 读不到内部控件（试过，只能拿到窗口），
    但它的 **UIA 树是完整的**（能读到 search 按钮、搜索结果、播放按钮等）。

依赖：comtypes（纯 Python 的小库）。没装或调用失败时本模块返回 None，
      调用方应退回原来的方式（详见 tool/music.py 的点歌流程）。
"""
import ctypes
import time

_cache = {"uia": None, "checked": False, "ok": False}


def available() -> bool:
    """UIA 能不能用（comtypes 是否就绪）"""
    if not _cache["checked"]:
        _cache["checked"] = True
        try:
            import comtypes.client as cc
            cc.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as UIA
            _cache["uia"] = cc.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
            _cache["ok"] = True
        except Exception as e:
            print(f"[UIA] ⚠ 不可用（{type(e).__name__}: {e}）→ 退回模拟键鼠方式")
            _cache["ok"] = False
    return bool(_cache["ok"])


def _mods():
    from comtypes.gen import UIAutomationClient as UIA
    return UIA


def root_for(hwnd):
    """窗口的 UIA 根元素"""
    if not available():
        return None
    try:
        return _cache["uia"].ElementFromHandle(int(hwnd))
    except Exception:
        return None


# 常用控件类型（UIA_*ControlTypeId）
CT_BUTTON = 50000
CT_EDIT = 50004
CT_HYPERLINK = 50005
CT_IMAGE = 50006          # 网易云的关闭"×"就是 Image（实测 name='close'）
CT_LISTITEM = 50007
CT_TEXT = 50033
CT_PANE = 50031
CT_SLIDER = 50026
CT_GROUP = 50020


def walk(root, max_depth: int = 16, limit: int = 800):
    """把 UIA 树摊平（生成 (element, name, control_type, automation_id)）"""
    if root is None:
        return
    if not available():
        return
    UIA = _mods()
    try:
        w = _cache["uia"].CreateTreeWalker(_cache["uia"].RawViewCondition)
    except Exception:
        return
    stack = [(root, 0)]
    n = 0
    while stack and n < limit:
        el, d = stack.pop()
        try:
            yield el, (el.CurrentName or ""), int(el.CurrentControlType), (el.CurrentAutomationId or "")
        except Exception:
            pass
        n += 1
        if d >= max_depth:
            continue
        try:
            ch = w.GetFirstChildElement(el)
        except Exception:
            ch = None
        k = 0
        while ch is not None and k < 300:
            stack.append((ch, d + 1))
            k += 1
            try:
                ch = w.GetNextSiblingElement(ch)
            except Exception:
                break


def find(root, name=None, contains=None, control_type=None, exact=False,
         automation_id=None):
    """找第一个匹配的元素（找不到返回 None）"""
    for el, nm, ct, aid in walk(root):
        if control_type is not None and ct != control_type:
            continue
        if automation_id is not None and aid != automation_id:
            continue
        if exact and name is not None and nm.strip() != name:
            continue
        if contains is not None and contains not in nm:
            continue
        if not exact and name is not None and nm.strip() != name and contains is None:
            continue
        return el
    return None


def find_all(root, name=None, contains=None, control_type=None, limit=20):
    out = []
    for el, nm, ct, aid in walk(root):
        if control_type is not None and ct != control_type:
            continue
        if contains is not None and contains not in nm:
            continue
        if name is not None and nm.strip() != name:
            continue
        out.append((el, nm, ct, aid))
        if len(out) >= limit:
            break
    return out


def rect_of(el):
    """元素的屏幕矩形 (l,t,r,b)（拿不到返回 None）"""
    try:
        r = el.CurrentBoundingRectangle
        return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except Exception:
        return None


def set_value(el, text: str) -> bool:
    """给输入框设值（**不需要焦点**）"""
    try:
        UIA = _mods()
        pat = el.GetCurrentPattern(UIA.UIA_ValuePatternId)
        if pat is None:
            return False
        p = pat.QueryInterface(UIA.IUIAutomationValuePattern)
        p.SetValue(str(text))
        return True
    except Exception as e:
        print(f"[UIA] ⚠ 设值失败: {type(e).__name__}: {e}")
        return False


def invoke(el) -> bool:
    """按按钮/链接的默认动作（**不需要焦点**）"""
    try:
        UIA = _mods()
        pat = el.GetCurrentPattern(UIA.UIA_InvokePatternId)
        if pat is None:
            return False
        p = pat.QueryInterface(UIA.IUIAutomationInvokePattern)
        p.Invoke()
        return True
    except Exception as e:
        print(f"[UIA] ⚠ 按下失败: {type(e).__name__}: {e}")
        return False


def find_all_fast(root, control_type=None, limit: int = 400):
    """用 UIA 自己的 FindAll 在**目标进程里**筛控件 —— 比 walk() 快 5~10 倍。

    为什么重要（2026-09-24 实测，网易云 741 个元素）：
        walk(limit=800)   0.68s   且只走到第 452 个 → 位置靠后的控件会漏（搜按钮在第 656 个！）
        walk(limit=2000)  1.07s
        FindAll(Edit)     0.22s   只回 1 个（就是搜索框）
        FindAll(Button)   0.24s   45 个按钮，search 按钮稳稳在里面
    点歌一次要来回找好几轮控件，用 walk 光遍历就三五秒，还时不时"找不到按钮"
    —— 这就是用户说的「点歌这么简单的事为什么这么慢/卡住」。
    """
    if root is None or not available():
        return []
    try:
        uia = _cache["uia"]
        UIA = _mods()
        if control_type is None:
            found = root.FindAll(4, uia.CreateTrueCondition())      # 4 = TreeScope_Descendants
        else:
            cond = uia.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, int(control_type))
            found = root.FindAll(4, cond)
        out = []
        try:
            n = int(found.Length)
        except Exception:
            return []
        for i in range(min(n, int(limit))):
            try:
                out.append(found.GetElement(i))
            except Exception:
                pass
        return out
    except Exception as e:
        print(f"[UIA] ⚠ FindAll 失败（{type(e).__name__}: {e}）→ 调用方应退回 walk")
        return []


def name_of(el) -> str:
    """控件名字（失败给空串）"""
    try:
        return str(el.CurrentName or "")
    except Exception:
        return ""


def aid_of(el) -> str:
    """控件 AutomationId（失败给空串）"""
    try:
        return str(el.CurrentAutomationId or "")
    except Exception:
        return ""


def children_count(root, max_depth: int = 3, limit: int = 30) -> int:
    """数一下树里有多少元素（用来判断"这棵树是不是空的"）。

    实测：网易云**窗口最小化**时，UIA 树里只剩窗口自己一个元素（子控件全没了）
    → 一看就知道是"读不到"而不是"没有搜索框"，调用方可据此先还原窗口。
    """
    n = 0
    for _ in walk(root, max_depth=max_depth, limit=limit):
        n += 1
    return n


def top_bar_edit(root, hwnd=None):
    """找顶部工具条里的那个输入框（搜索框）。

    ★ 实测教训（2026-09-23）：**不能按名字认**。这台机器上网易云有两个 Edit：
        name='苦茶子 - Starling8'  rect=(703,116,915,146)   ← 顶部搜索框（内容就是歌名）
        name='搜索'                rect=(1463,378,1503,408) ← 别处的框（名字反倒像"搜索"）
      按名字挑会挑错 → 搜错 → 放了别的歌。所以**认位置**：最靠上的那个就是顶栏。

    用 FindAll(Edit) 取（实测 0.22s，walk 要 0.7~1.1s 还可能漏）；
    拿不到位置时才退回"名字/标识带 search/搜索"的那个。
    注意：窗口最小化时一个 Edit 都读不到（UIA 树是空的）——那不是这里的锅，
    调用方应先把窗口还原（见 tool/music.py 的 ensure_uia）。
    """
    els = find_all_fast(root, CT_EDIT, limit=40)
    if not els:
        # 退回旧的全树遍历（万一 FindAll 在这个控件上不工作）
        for _el, nm, ct, _aid in walk(root, limit=2000):
            if ct == CT_EDIT:
                els.append(_el)
    if not els:
        return None
    cands = []
    hint = None
    for idx, el in enumerate(els):
        nm, aid = name_of(el), aid_of(el)
        if hint is None and ("search" in f"{nm} {aid}".lower() or "搜索" in nm):
            hint = el
        r = rect_of(el)
        cands.append((r[1] if r else None, idx, el))
    heightable = [c for c in cands if c[0] is not None]
    if heightable:
        heightable.sort(key=lambda x: (x[0], x[1]))
        return heightable[0][2]          # 顶栏 = 最靠上的输入框
    if hint is not None:
        return hint
    return cands[0][2]


def buttons_named(root, contains="", limit: int = 400):
    """所有名字含 contains 的按钮 [(el, name, rect)]（用 FindAll，快）"""
    out = []
    for el in find_all_fast(root, CT_BUTTON, limit=limit):
        nm = name_of(el)
        if contains and contains not in nm:
            continue
        out.append((el, nm, rect_of(el)))
    return out


def button_next_to(root, box_rect, limit: int = 400):
    """紧挨着某个输入框左边的那个按钮（= 放大镜/搜索键，按位置认）。

    为什么要这个兜底：网易云的 search 按钮在整棵树里排得很靠后（实测第 656 个），
    窗口刚从最小化还原时树还没长全 → 按名字可能找不到；但"贴着搜索框左边"
    这个位置关系很稳（实测按钮 rect=(657,117,703,145)、搜索框 rect=(703,116,915,146)）。
    """
    if not box_rect:
        return None, None
    bl, bt, br, bb = box_rect
    best = None
    for el in find_all_fast(root, CT_BUTTON, limit=limit):
        r = rect_of(el)
        if not r:
            continue
        l, t, rr, b = r
        if rr <= bl + 6 and (bl - rr) <= 60 and t < bb and b > bt:   # 右缘贴着框左边 + 纵向重叠
            score = abs(bl - rr) + abs(((t + b) // 2) - ((bt + bb) // 2))
            if best is None or score < best[0]:
                best = (score, el, name_of(el), r)
    if best:
        return best[1], best[3]
    return None, None


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("comtypes/UIA 可用:", available())
    hwnd = ctypes.windll.user32.FindWindowW("OrpheusBrowserHost", None)
    print("网易云窗口:", hwnd)
    root = root_for(hwnd)
    if root is None:
        raise SystemExit("拿不到 UIA 根元素")
    print("窗口名:", root.CurrentName[:40])
    ed = top_bar_edit(root, hwnd)
    print("顶部输入框:", rect_of(ed) if ed is not None else "没找到")
    btn = find(root, control_type=CT_BUTTON, contains="search")
    print("搜索按钮:", (btn.CurrentName, rect_of(btn)) if btn is not None else "没找到")
    pl = find(root, control_type=CT_BUTTON, contains="播放")
    print("播放按钮:", (pl.CurrentName, rect_of(pl)) if pl is not None else "没找到")
