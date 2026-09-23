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


def top_bar_edit(root, hwnd):
    """找顶部工具条里的那个输入框（搜索框）：所有 Edit 里最靠上的那个"""
    cands = []
    for el, nm, ct, aid in walk(root):
        if ct == CT_EDIT:
            r = rect_of(el)
            if r:
                cands.append((r[1], el, nm, r))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    return cands[0][1]


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
