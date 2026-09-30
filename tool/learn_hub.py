# -*- coding: utf-8 -*-
"""联网学习中枢（2026-09-30 新增）。

背景：启动器插件页里有两个"联网学习"相关的官方插件 ——
  · `auto_learning`（自主学习：问题自动联网搜索 / 群媒体学习）
  · `slang_search`（网络用语自动查询）
它们的开关当初只对着 QQ 写（配置键都是 `qq_*`），实现也直接调 `qq.qq_search` /
`qq.qq_slang`，于是**微信和桌宠用不上**（用户 2026-09-30：「能不能拓展一下，
变成微信，QQ，桌宠都可以使用的东西」）。

这个模块把"要不要联网查、查到的内容怎么拼进提示词"抽出来，三条渠道共用：
  · QQ    → `qq/qq_chat.py` 调 `fact_prefix(text, "qq")`
  · 微信  → `wechat/wechat_bridge.py` 用 `push_channel("wx")` 包住回复调用
  · 桌宠  → `tool/chat.py` / `tool/cloud_API_chat.py` 调 `fact_prefix(text, current_channel())`

开关口径（保持老用户行为不变）：
  · 插件总开关仍是插件页那两个键（`qq_auto_learn_enable` / `qq_slang_enable`）——
    键名带 qq_ 是历史遗留，但**现在管所有渠道**；
  · 子开关（`qq_auto_learn_search`）同样对所有渠道生效；
  · 每条渠道另有独立开关，默认开：`learn_search_qq/wx/pet`、`learn_slang_qq/wx/pet`
    （想只让桌宠查，就把另外两个关掉）。

⚠ 本模块**不依赖 Qt**，也不 import QQ 运行时；QQ 相关的重库都是用到时才懒加载，
拿不到就当"这个渠道查不了"，绝不让桌宠/微信因为 QQ 侧缺库而崩。
"""
import os
import threading

CHANNELS = ("qq", "wx", "pet")
CHANNEL_NAMES = {"qq": "QQ", "wx": "微信", "pet": "桌宠"}
DEFAULT_CHANNEL = "pet"

_local = threading.local()


def _cfg(key, default=None):
    try:
        from tool.config import get_config
        return get_config("./config.json").get(key, default)
    except Exception:
        return default


def _bool(key, default=False) -> bool:
    try:
        from tool.config import as_bool
        return as_bool(_cfg(key, "true" if default else "false"), default)
    except Exception:
        return bool(default)


# ── 当前渠道（线程内上下文；不设就是桌宠）─────────────────────────
def push_channel(channel: str):
    """把这根线程标记成某个渠道（微信桥回复前调；用完记得 pop_channel）"""
    _local.channel = str(channel or DEFAULT_CHANNEL)


def pop_channel():
    try:
        del _local.channel
    except Exception:
        pass


def current_channel() -> str:
    ch = getattr(_local, "channel", None)
    return ch if ch in CHANNELS else DEFAULT_CHANNEL


def current_channel_or(default: str) -> str:
    """本线程没显式标过渠道时，用调用方给的默认值。

    QQ 的对话封装 `qq/qq_chat.py` 被两条链路复用：
      · QQ 桥自己（没标记）→ 默认 "qq"
      · 微信桥（用 learn_hub.channel("wx") 包住）→ "wx"
    所以 qq_chat 里要用 current_channel_or("qq")，不能用 current_channel()（那是桌宠）。
    """
    ch = getattr(_local, "channel", None)
    if ch in CHANNELS:
        return ch
    return default if default in CHANNELS else DEFAULT_CHANNEL


class channel:
    """with learn_hub.channel("wx"): ... —— 包住微信侧的回复调用"""

    def __init__(self, name):
        self.name = str(name or DEFAULT_CHANNEL)

    def __enter__(self):
        self._old = getattr(_local, "channel", None)
        push_channel(self.name)
        return self

    def __exit__(self, *exc):
        if self._old is None:
            pop_channel()
        else:
            _local.channel = self._old
        return False


# ── 开关 ────────────────────────────────────────────────────────
def search_enabled(channel_name: str = "") -> bool:
    """「问题自动联网搜索」在这个渠道能不能用"""
    ch = channel_name or current_channel()
    if ch not in CHANNELS:
        return False
    if not _bool("qq_auto_learn_enable", False):        # 插件总开关（历史键名）
        return False
    if not _bool("qq_auto_learn_search", False):        # 子开关（对所有渠道生效）
        return False
    return _bool("learn_search_%s" % ch, True)          # 渠道开关（默认开）


def slang_enabled(channel_name: str = "") -> bool:
    """「网络用语自动查询」在这个渠道能不能用"""
    ch = channel_name or current_channel()
    if ch not in CHANNELS:
        return False
    if not _bool("qq_slang_enable", False):             # 插件总开关（历史键名）
        return False
    return _bool("learn_slang_%s" % ch, True)


def status_text() -> str:
    """给状态页/自检看的一行摘要"""
    bits = []
    for ch in CHANNELS:
        bits.append("%s:%s/%s" % (CHANNEL_NAMES[ch],
                                  "查" if search_enabled(ch) else "-",
                                  "梗" if slang_enabled(ch) else "-"))
    return " ".join(bits)


# ── 实际查询（懒加载 QQ 侧实现，失败就算查不到）──────────────────
def search_note(user_text: str, img_desc: str = "") -> str:
    """联网搜索这个问题的答案要点（查不到返回空串）"""
    try:
        if not user_text and not img_desc:
            return ""
        from qq.qq_search import note_for_text
        return note_for_text(user_text, img_desc=img_desc) or ""
    except Exception as e:
        print("[LearnHub] ⚠ 联网搜索不可用: %s" % e)
        return ""


def is_link(user_text: str) -> bool:
    try:
        from qq.qq_search import is_link as _il
        return bool(_il(user_text))
    except Exception:
        return False


def slang_note(user_text: str) -> str:
    """网络用语/黑话的含义（不懂才查、查不到返回空串）"""
    try:
        if not user_text:
            return ""
        from qq.qq_slang import lookup
        return lookup(user_text) or ""
    except Exception as e:
        print("[LearnHub] ⚠ 网络用语查询不可用: %s" % e)
        return ""


def learn_notes(user_text: str, gid=None) -> list:
    """群学习库检索（只有 QQ 群聊有库；其它渠道 gid=None → 返回空）"""
    if gid is None or not user_text or len(user_text) > 120:
        return []
    try:
        from qq.qq_learnstore import retrieve
        return list(retrieve(user_text, gid=gid) or [])
    except Exception:
        return []


def fact_prefix(user_text: str, channel_name: str = "", img_desc: str = "",
                gid=None) -> str:
    """拼给提示词的「事实前缀」：联网搜索 + 网络用语 + 群学习库。

    三条渠道都调它；没开/查不到就返回空串（调用方直接拼上去即可）。
    """
    ch = channel_name or current_channel()
    out = []
    if search_enabled(ch):
        note = search_note(user_text, img_desc=img_desc)
        if note:
            out.append(note)
        elif is_link(user_text):
            out.append("【链接提示】系统已尝试代为打开该链接但未能提取到内容"
                       "（网站可能要登录或开启了反爬）。你不需要打开任何网页，"
                       "请如实说暂时没看到内容并请对方直接说说大概是什么，不要编造。")
    if slang_enabled(ch):
        note = slang_note(user_text)
        if note:
            out.append(note)
    notes = learn_notes(user_text, gid=gid)
    if notes:
        out.append("【群学习参考】" + "\n".join(notes))
    return ("\n".join(x for x in out if x) + "\n") if out else ""


def reset_cache():
    """测试/切换角色用：清掉线程标记"""
    pop_channel()


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("当前渠道:", current_channel())
    print("开关状态:", status_text())
    with channel("wx"):
        print("with 里:", current_channel())
    print("with 外:", current_channel())
