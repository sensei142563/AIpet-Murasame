# -*- coding: utf-8 -*-
"""无障碍（MSAA）后台操作：直接给控件设值/按按钮，**不抢焦点、不动鼠标、不切窗口**。

为什么做这个：主人要求"后台窗口执行不显示窗口进行执行任务"。
网易云客户端是 CEF 界面，模拟键鼠必须先把窗口切到最前面（会打断他在做的事），
而 MSAA 的 IAccessible 可以直接：
    put_accValue(搜索框, "歌名")  →  accDoDefaultAction(搜索结果里的「播放」按钮)
全程窗口可以一直待在后台。

实现方式：ctypes 手工调 COM。IAccessible 继承 IDispatch，方法在虚表上的顺序是固定的：
    IUnknown 0~2 | IDispatch 3~6 | get_accParent 7, get_accChildCount 8, get_accChild 9,
    get_accName 10, get_accValue 11, get_accDescription 12, get_accRole 13, get_accState 14,
    get_accHelp 15, get_accHelpTopic 16, get_accKeyboardShortcut 17, get_accFocus 18,
    get_accSelection 19, get_accDefaultAction 20, accSelect 21, accLocation 22,
    accNavigate 23, accHitTest 24, accDoDefaultAction 25, put_accName 26, put_accValue 27
所以直接按索引取函数指针就够了，不用 IDispatch::Invoke 那套 VARIANT。
"""
import ctypes
import ctypes.wintypes as wt

OBJID_CLIENT = 0xFFFFFFFC
CHILDID_SELF = 0

# IAccessible 常用角色（accRole 的返回值）
ROLE_SYSTEM_PUSHBUTTON = 0x2B
ROLE_SYSTEM_TEXT = 0x2A
ROLE_SYSTEM_LINK = 0x1E
ROLE_SYSTEM_LIST = 0x21
ROLE_SYSTEM_LISTITEM = 0x22
ROLE_SYSTEM_GROUPING = 0x14
ROLE_SYSTEM_CLIENT = 0xA

_ROLE_NAMES = {
    ROLE_SYSTEM_PUSHBUTTON: "button", ROLE_SYSTEM_TEXT: "text",
    ROLE_SYSTEM_LINK: "link", ROLE_SYSTEM_LIST: "list",
    ROLE_SYSTEM_LISTITEM: "listitem", ROLE_SYSTEM_GROUPING: "group",
}


class VARIANT(ctypes.Structure):
    """只要能放 childid（VT_I4）的最小 VARIANT"""
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                ("r3", ctypes.c_ushort), ("val", ctypes.c_longlong)]


def _var_i4(v: int) -> VARIANT:
    x = VARIANT()
    x.vt = 3                      # VT_I4
    x.val = int(v)
    return x


def _func(ptr, index: int):
    """取 COM 对象虚表里第 index 个方法"""
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    addr = vtbl[index]
    return ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(addr)


class Acc:
    """一层封装：拿一个 IAccessible 指针，按方法名调用"""

    def __init__(self, ptr):
        self.ptr = ctypes.c_void_p(int(ptr))

    def _call(self, index: int, restype, argtypes, *args):
        fn = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(_addr(self.ptr.value, index))
        return fn(self.ptr, *args)

    # ── 常用属性 ──
    def child_count(self) -> int:
        v = ctypes.c_long(0)
        try:
            self._call(8, ctypes.c_long, [ctypes.POINTER(ctypes.c_long)], ctypes.byref(v))
        except Exception:
            return 0
        return int(v.value)

    def child(self, child_id: int):
        """返回子对象的 IAccessible 指针（拿不到返回 None）"""
        out = ctypes.c_void_p(0)
        var = _var_i4(child_id)
        try:
            hr = self._call(9, ctypes.c_long, [VARIANT, ctypes.POINTER(ctypes.c_void_p)],
                            var, ctypes.byref(out))
            if hr == 0 and out.value:
                return Acc(out.value)
        except Exception:
            pass
        return None

    def _bstr_get(self, index: int, child_id: int = CHILDID_SELF):
        p = ctypes.c_void_p(0)
        var = _var_i4(child_id)
        try:
            hr = self._call(index, ctypes.c_long, [VARIANT, ctypes.POINTER(ctypes.c_void_p)],
                            var, ctypes.byref(p))
            if hr != 0 or not p.value:
                return ""
            s = ctypes.c_wchar_p(p.value).value or ""
            try:
                ctypes.windll.oleaut32.SysFreeString(p)
            except Exception:
                pass
            return str(s)
        except Exception:
            return ""

    def name(self, child_id: int = CHILDID_SELF) -> str:
        return self._bstr_get(10, child_id)

    def value(self, child_id: int = CHILDID_SELF) -> str:
        return self._bstr_get(11, child_id)

    def default_action(self, child_id: int = CHILDID_SELF) -> str:
        return self._bstr_get(20, child_id)

    def role(self, child_id: int = CHILDID_SELF) -> int:
        v = ctypes.c_long(0)
        var = _var_i4(child_id)
        try:
            self._call(13, ctypes.c_long, [VARIANT, ctypes.POINTER(ctypes.c_long)],
                       var, ctypes.byref(v))
        except Exception:
            return 0
        return int(v.value)

    def do_action(self, child_id: int = CHILDID_SELF) -> bool:
        """按默认动作（按钮=按下、链接=打开）"""
        var = _var_i4(child_id)
        try:
            return self._call(25, ctypes.c_long, [VARIANT], var) == 0
        except Exception:
            return False

    def set_value(self, text: str, child_id: int = CHILDID_SELF) -> bool:
        """给输入框设值（**不需要焦点**）"""
        var = _var_i4(child_id)
        try:
            return self._call(27, ctypes.c_long, [VARIANT, ctypes.c_wchar_p],
                              var, ctypes.c_wchar_p(str(text))) == 0
        except Exception:
            return False


def _addr(ptr_value, index: int):
    vtbl = ctypes.cast(ctypes.c_void_p(int(ptr_value)),
                       ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return vtbl[index]


def of_window(hwnd):
    """取某个窗口的 IAccessible（拿不到返回 None）"""
    try:
        iid = ctypes.c_char_p(b"")
        # IID_IAccessible = {618736E0-3C3D-11CF-810C-00AA00389B71}
        import uuid
        iid = (ctypes.c_byte * 16)()
        ctypes.memmove(iid, uuid.UUID("{618736E0-3C3D-11CF-810C-00AA00389B71}").bytes_le, 16)
        p = ctypes.c_void_p(0)
        hr = ctypes.windll.oleacc.AccessibleObjectFromWindow(
            ctypes.c_void_p(int(hwnd)), ctypes.c_ulong(OBJID_CLIENT),
            ctypes.byref(iid), ctypes.byref(p))
        if hr == 0 and p.value:
            return Acc(p.value)
    except Exception:
        pass
    return None


def walk(acc: Acc, depth: int = 0, max_depth: int = 12, out: list = None):
    """把整棵无障碍树摊平成 [(child_id, role, name, value)]（child_id 是相对父节点的）"""
    if out is None:
        out = []
    if depth > max_depth:
        return out
    try:
        n = acc.child_count()
    except Exception:
        n = 0
    for i in range(1, min(n, 400) + 1):
        try:
            ch = acc.child(i)
            if ch is None:
                # 简单子元素（没有独立接口）→ 用 child_id 读属性
                role = acc.role(i)
                nm = acc.name(i)
                if nm or role:
                    out.append((i, role, nm, acc.value(i)))
                continue
            nm = ch.name() or acc.name(i)
            out.append((i, ch.role(), nm, ch.value()))
            walk(ch, depth + 1, max_depth, out)
        except Exception:
            continue
    return out


def find(acc: Acc, contains: str = "", role: int = 0, exact: bool = False):
    """在树里找第一个匹配的控件 → (子对象, child_id, role, name, value)"""
    try:
        n = acc.child_count()
    except Exception:
        n = 0
    for i in range(1, min(n, 400) + 1):
        try:
            ch = acc.child(i)
            if ch is None:
                nm = acc.name(i)
                rl = acc.role(i)
                if _hit(nm, contains, exact) and (not role or rl == role):
                    return acc, i, rl, nm, acc.value(i)
                continue
            nm = ch.name() or acc.name(i)
            rl = ch.role()
            if _hit(nm, contains, exact) and (not role or rl == role):
                return ch, i, rl, nm, ch.value()
            got = find(ch, contains, role, exact)
            if got:
                return got
        except Exception:
            continue
    return None


def _hit(name: str, contains: str, exact: bool) -> bool:
    if not contains:
        return True
    if exact:
        return str(name).strip() == contains
    return contains in str(name)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    hwnd = ctypes.windll.user32.FindWindowW("OrpheusBrowserHost", None)
    print("网易云窗口:", hwnd)
    acc = of_window(hwnd) if hwnd else None
    if acc is None:
        print("✗ 拿不到无障碍接口")
        raise SystemExit
    print("子元素数量:", acc.child_count())
    flat = walk(acc)
    print("摊平后元素数量:", len(flat))
    print()
    print("=== 找搜索框（text 类）===")
    got = find(acc, role=ROLE_SYSTEM_TEXT)
    print("  ", got[1:] if got else "没找到")
    print()
    print("=== 找「播放」按钮 ===")
    got2 = find(acc, contains="播放")
    print("  ", got2[1:] if got2 else "没找到")
    print()
    print("=== 前 20 个元素 ===")
    for cid, role, nm, val in flat[:20]:
        print("   id=%-4s role=%-12s name=%s value=%s" % (cid, _ROLE_NAMES.get(role, role), nm[:30], val[:20]))
