# -*- coding: utf-8 -*-
"""自主行动分档：哪些事她自己可以做，哪些必须等主人开口。

参考几个开源桌宠项目对"自主性"的处理（能力越大越要划边界），分三档：

    safe   她自己也能做：移动鼠标、滚轮、点击/双击/右键、看屏幕、放音乐、读文件
           （点击本身不会丢数据，而且已有坐标校验和重复抑制兜着）
    ask    只在主人开口时做：**打字、按单键、按组合键**
           （往当前窗口敲字很危险 —— 可能敲进主人的编辑器；组合键更狠，比如 alt+f4）
    never  永远不做：系统目录、注册表、关机/注销、批量删除之类

危险组合键（alt+f4 / win+l / ctrl+shift+esc…）也归到 ask：
主人明确说"关掉这个窗口"时可以用，她自己想起来就按 —— 不行。
"""
import re

TIER_SAFE = "safe"
TIER_ASK = "ask"
TIER_NEVER = "never"

_SAFE_TYPES = ("move", "wait", "scroll", "click", "double", "right", "screenshot", "music", "file_read")
_ASK_TYPES = ("type", "key", "hotkey")

# 危险组合键（主人开口才做）
_DANGER_KEYS = ("alt+f4", "alt+f4", "win+l", "ctrl+shift+esc", "ctrl+alt+del",
                "alt+shift", "ctrl+alt+delete", "win+d", "ctrl+w")
# 永远不碰的文字意图（她就算想也不给做）
_NEVER_TEXT = ("格式化", "关机", "重启", "注销", "注册表", "删除系统", "清空回收站",
               "regedit", "shutdown", "format", "del /f", "rm -rf", "taskkill /f /im")


def tier_of_action(action: dict) -> str:
    """给一个动作分档"""
    try:
        t = str((action or {}).get("type") or "").lower()
        if t in _SAFE_TYPES:
            return TIER_SAFE
        if t == "hotkey":
            keys = "+".join(str(k).lower() for k in ((action or {}).get("keys") or []))
            if keys in _DANGER_KEYS:
                return TIER_ASK
            return TIER_ASK
        if t in _ASK_TYPES:
            return TIER_ASK
        return TIER_ASK
    except Exception:
        return TIER_ASK


def tier_of_text(text: str) -> str:
    """给一句话/一条指令分档（主要用来拦"永远不做"的那类）"""
    t = str(text or "")
    low = t.lower()
    for w in _NEVER_TEXT:
        if w in t or w in low:
            return TIER_NEVER
    return TIER_ASK


def allowed(action_or_text, is_auto: bool) -> tuple:
    """现在允许做吗 → (允许?, 原因)

    is_auto=True 表示这是她自己想做的（主人没开口）。
    """
    try:
        if isinstance(action_or_text, dict):
            tier = tier_of_action(action_or_text)
        else:
            tier = tier_of_text(action_or_text)
        if tier == TIER_NEVER:
            return False, "这类操作（系统/删除/关机之类）我永远不碰"
        if tier == TIER_ASK and is_auto:
            return False, "这种操作（打字/按键）要等主人开口我才做"
        return True, ""
    except Exception:
        return True, ""


def note() -> str:
    """给模型的一句话（让她自己知道边界，省得白试）"""
    return ("【你能自己做到哪一步】你自己想动手时，可以做：移动鼠标、滚轮、点击/双击/右键、"
            "看屏幕、放音乐、看你允许我读的文件；但**打字、按单键、按组合键**这类"
            "（容易敲进主人的编辑器）要等主人开口再做；系统目录、删除、关机这些永远不做。")


def summary_text() -> str:
    return ("可自主：移动 / 滚轮 / 点击 / 看屏幕 / 放音乐 / 读允许的文件\n"
            "需主人开口：打字 / 按键 / 组合键（alt+f4 这类）\n"
            "永不允许：系统目录 / 注册表 / 关机重启 / 删除")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cases = [
        ({"type": "click", "x": 800, "y": 250}, True, "自主点一下"),
        ({"type": "type", "text": "你好"}, True, "自主打字（该拦）"),
        ({"type": "type", "text": "你好"}, False, "主人让她打字"),
        ({"type": "hotkey", "keys": ["alt", "f4"]}, True, "自主 alt+f4（该拦）"),
        ({"type": "hotkey", "keys": ["ctrl", "s"]}, False, "主人让她 ctrl+s"),
        ({"type": "move", "x": 1, "y": 1}, True, "自主移动"),
        ("帮我格式化 C 盘", False, "格式化（永远不做）"),
    ]
    for act, auto, name in cases:
        ok, why = allowed(act, auto)
        print("  %-24s 自主=%-5s → %-6s %s" % (name, auto, "允许" if ok else "拦下", why))
    print()
    print(summary_text())
