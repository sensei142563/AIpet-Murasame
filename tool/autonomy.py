# -*- coding: utf-8 -*-
"""自主行动分档：哪些事她自己可以做，哪些必须等主人开口。

为什么要有
----------
能力越大越要划边界。三档：

    safe   她自己也能做：**只读/信息类** —— 看、读、查、搜、总结、统计、截图、翻译、列出、对比
           （这些不会改变电脑上的东西，做了最多是多看一眼）
    ask    只在主人开口时做：**会改动电脑或往外发东西的** —— 打开、运行、输入、打字、点击、
           按键、组合键、写、改、删、安装、下载、发送、上传、提交、登录、付款
           （往当前窗口敲字很危险：可能敲进主人的编辑器；组合键更狠，比如 alt+f4）
    never  永远不做：格式化、关机/重启、注册表、删系统目录、清空回收站、diskpart…

与 config 的 `autonomy_level` 的关系
----------------------------------
    quiet   安静：她自己**不主动动手**（只回应主人；提醒照常）
    normal  适中：只读的事她自己可以做
    active  活跃：只读的事自己做，"会改动"的事**可以提议**（但仍然要主人点头）

在本仓库里怎么落地
----------------
我们没有原生动作执行器，执行交给 agent 桥接（`tool/agent_bridge.py`）——
所以这里的 `allowed(task, is_auto)` 判的是**任务文本**；桥接在跑之前会来问一次：
never 直接拒、其它照旧弹确认框。给动作字典留的 `tier_of_action()` 也保留（将来若有原生动作直接用）。
"""
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TIER_SAFE = "safe"
TIER_ASK = "ask"
TIER_NEVER = "never"

# 动作字典（原生动作用；与 agent 桥接无关，但保留同构的判定）
_SAFE_TYPES = ("move", "wait", "scroll", "click", "double", "right", "screenshot",
               "music", "file_read")
_ASK_TYPES = ("type", "key", "hotkey")
_DANGER_KEYS = ("alt+f4", "win+l", "ctrl+shift+esc", "ctrl+alt+del", "ctrl+alt+delete",
                "win+d", "ctrl+w", "alt+shift")

# 任务文本：永远不碰（先判这一档）
_NEVER_TEXT = ("格式化", "关机", "重启", "注销", "注册表", "删除系统", "删掉系统", "清空回收站",
               "regedit", "shutdown", "format ", "format c", "del /f", "del /s", "rm -rf",
               "taskkill /f", "diskpart", "bcdedit", "vssadmin", "cipher /w")
# 她自己能做的（只读/信息类）
_SAFE_TEXT = ("看一下", "看看", "看眼", "读一下", "读读", "读文件", "查一下", "查查", "查询",
              "搜一下", "搜搜", "搜索", "总结", "统计", "截图", "截屏", "翻译", "念一下",
              "列出", "列一下", "对比", "算一下", "算算", "是什么", "有多少", "在哪")
# 其余一律按"要主人开口"处理（保守默认）
# 自然说法变化多，几类常用的用正则兜住（"截个屏/截张图/截一下屏幕"都算只读）
_SAFE_RE = (re.compile(r"截(个|一|张|下)*\s*(图|屏|屏幕)"),)


def classify(action_or_text) -> str:
    """给动作字典或任务文本分档 → safe / ask / never"""
    try:
        if isinstance(action_or_text, dict):
            return tier_of_action(action_or_text)
        return tier_of_text(action_or_text)
    except Exception:
        return TIER_ASK


def tier_of_action(action: dict) -> str:
    """给一个动作字典分档"""
    try:
        t = str((action or {}).get("type") or "").lower()
        if t in _SAFE_TYPES:
            return TIER_SAFE
        if t == "hotkey":
            return TIER_ASK                       # 组合键一律要主人开口
        if t in _ASK_TYPES:
            return TIER_ASK
        return TIER_ASK
    except Exception:
        return TIER_ASK


def tier_of_text(text: str) -> str:
    """给一句话/一条任务分档（先拦"永远不做"，再认"只读"）"""
    t = str(text or "")
    low = t.lower()
    for w in _NEVER_TEXT:
        if w in t or w in low:
            return TIER_NEVER
    for w in _SAFE_TEXT:
        if w in t or w in low:
            return TIER_SAFE
    for rx in _SAFE_RE:
        if rx.search(t):
            return TIER_SAFE
    return TIER_ASK


def level() -> str:
    """当前活跃度档位（取自 tool.desire；没有它就按 normal）"""
    try:
        from tool import desire as _dz
        return _dz.level()
    except Exception:
        return "normal"


def level_label() -> str:
    return {"quiet": "安静", "normal": "适中", "active": "活跃"}.get(level(), "适中")


def allowed(action_or_text, is_auto: bool, lv: str = None) -> tuple:
    """现在允许做吗 → (允许?, 原因)

    is_auto=True 表示这是**她自己想做的**（主人没开口）。
    """
    try:
        tier = classify(action_or_text)
        if tier == TIER_NEVER:
            return False, "这类操作（系统/删除/关机之类）我永远不碰"
        _lv = str(lv if lv is not None else level())
        if is_auto and _lv == "quiet":
            return False, "活跃度=安静：我不主动动手（只回应主人）"
        if tier == TIER_ASK and is_auto:
            return False, "这种操作（会改动电脑/往外发东西）要等主人开口我才做"
        return True, ""
    except Exception:
        return True, ""


def may_propose(action_or_text, lv: str = None) -> bool:
    """她自己能不能**提议**做这件事（提议 ≠ 自己做：仍然要主人点头）

    · never → 连提都不提
    · safe  → 安静档不提（她自己不主动），其它档可以提
    · ask   → 只有"活跃"档才会主动提议（"安静/适中"档等她想到就太吵了）
    """
    try:
        tier = classify(action_or_text)
        _lv = str(lv if lv is not None else level())
        if tier == TIER_NEVER or _lv == "quiet":
            return False
        if tier == TIER_SAFE:
            return True
        return _lv == "active"
    except Exception:
        return False


def tier_label(tier: str = None, action_or_text=None) -> str:
    t = tier or classify(action_or_text)
    return {TIER_SAFE: "只读（她自己也能做）", TIER_ASK: "会改动电脑（要主人开口）",
            TIER_NEVER: "危险（永远不做）"}.get(t, t)


def note() -> str:
    """给模型的一句话（让她自己知道边界，省得白试）"""
    return ("【你能自己做到哪一步】你自己想动手时，可以做：看屏幕、读、查、搜、总结、统计、"
            "截图、翻译这类**只读**的事；但打开/运行/输入文字/按键/组合键/删改/安装/发送"
            "这类**会改动电脑或往外发东西**的，要等主人开口再做；"
            "系统目录、注册表、关机重启、删除这些**永远不做**（就算主人让你做也别做）。"
            "需要动手时按 /agent 那条路走，会先问过主人。")


def summary_text() -> str:
    return ("当前自主性：%s\n"
            "可自主：看屏幕 / 读 / 查 / 搜 / 总结 / 统计 / 截图 / 翻译（只读）\n"
            "需主人开口：打开 / 运行 / 打字 / 按键 / 组合键 / 删改 / 安装 / 发送\n"
            "永不允许：系统目录 / 注册表 / 关机重启 / 格式化 / 批量删除" % level_label())


if __name__ == "__main__":
    cases = [
        ({"type": "click", "x": 800, "y": 250}, True, "自主点一下（动作字典）"),
        ({"type": "type", "text": "你好"}, True, "自主打字（该拦）"),
        ({"type": "hotkey", "keys": ["alt", "f4"]}, True, "自主 alt+f4（该拦）"),
        ("看看现在屏幕上是什么", True, "自主看一眼（允许）"),
        ("帮我查一下今天的天气", True, "自主查一下（允许）"),
        ("帮我把记事本打开", True, "自主打开软件（该拦）"),
        ("帮我把记事本打开", False, "主人让它打开（允许）"),
        ("帮我格式化 C 盘", False, "格式化（永远不做）"),
    ]
    for act, auto, name in cases:
        ok, why = allowed(act, auto)
        print("  %-26s 自主=%-5s → %-6s %s" % (name, auto, "允许" if ok else "拦下", why))
    print()
    print(summary_text())
