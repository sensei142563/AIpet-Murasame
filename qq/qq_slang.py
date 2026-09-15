# -*- coding: utf-8 -*-
"""
网络用语/梗 查询 — 群里出现看不懂的短黑话时自动上网查一下意思再接话。

触发（克制，避免每条消息都联网）：
1. 文本含「XX什么意思 / 什么梗 / 是啥意思」这类询问 → 提取被问的词去查；
2. 整句很短（≤20 个有效字符）、不是常见寒暄、且不是命令/长句 → 当作疑似网络语整句查询。
   附加限流：每次对话进程 15 秒内最多查一次，避免群聊刷屏连搜。

查询：必应国内版网页搜索（cn.bing.com），解析第一条结果的标题+摘要。
结果缓存 24 小时（data/qq_slang_cache.json），同一词不重复搜索。
所有失败静默降级（返回 None），绝不影响正常对话。
"""

import os
import re
import json
import time
import threading

import requests

from tool.paths import data_path

CACHE_FILE = data_path("data", "qq_slang_cache.json")
CACHE_HOURS = 24
CACHE_MAX = 200

_lock = threading.Lock()
_last_search_ts = 0.0          # 进程内防抖：两次联网搜索至少间隔 15 秒
_MIN_INTERVAL = 15.0

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 常见寒暄/无意义短句（命中则不查）
_SKIP_SET = {
    "你好", "你好呀", "在吗", "在么", "在不在", "早上好", "早安", "中午好", "下午好",
    "晚上好", "晚安", "拜拜", "再见", "谢谢", "多谢", "哈哈", "哈哈哈", "呵呵",
    "嘿嘿", "嗯嗯", "嗯", "好的", "好", "好呀", "行", "行吧", "哦", "哦哦", "来了",
    "在的", "没", "有", "啥", "啥呢", "干嘛", "干啥", "喂", "诶", "嗨", "hi", "hello",
    "对", "对的", "是", "是啊", "没错", "确实", "无语", "离谱", "草", "卧槽", "我靠",
}


def _norm_text(text: str) -> str:
    """去空白/标点/emoji，只留有效字符（用于长度判断）"""
    t = re.sub(r"[\s\u3000]+", "", text or "")
    t = re.sub(r"[，。！？、；：""''（）【】《》…—·,.!?;:'\"()\[\]{}<>@#*&%$￥~`|/\\^]", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", t)  # emoji
    return t


def _looks_question(text: str):
    """是否「XX什么意思/什么梗」式问句 → 返回要查的词或 None"""
    m = re.search(r"([^\s，。！？、；,;!?]{1,12}?)(?:什么|啥)(?:意思|梗|含义)|(?:什么意思|啥意思|什么梗)[:：]?\s*([^\s，。！？、；]{1,12})", text or "")
    if m:
        w = (m.group(1) or m.group(2) or "").strip()
        # 去掉尾巴上被带进来的虚词（"处吗是" → "处吗"）
        w = re.sub(r"[是的了嘛呢吧啊呀哦么]+$", "", w)
        return w
    return None


def _read_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _write_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def _search_bing(term: str) -> str:
    """必应搜索，返回第一条结果的「标题 —— 摘要」，失败返回 None"""
    q = f"{term} 意思 梗"
    try:
        resp = requests.get(
            "https://cn.bing.com/search",
            params={"q": q},
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=6,
        )
        if resp.status_code != 200:
            return None
        html = resp.text
        # 第一条搜索结果：<li class="b_algo"> ... <h2><a>标题</a></h2> ... <p>摘要</p>
        m = re.search(r'<li class="b_algo"[\s\S]*?<h2[^>]*><a[^>]*>([\s\S]*?)</a></h2>'
                      r'[\s\S]*?(?:<p[^>]*>([\s\S]*?)</p>)?', html)
        if not m:
            return None
        title = _strip_html(m.group(1))
        snippet = _strip_html(m.group(2)) if m.group(2) else ""
        title = re.sub(r"\s+", " ", title)[:80]
        snippet = re.sub(r"\s+", " ", snippet)[:220]
        if not title and not snippet:
            return None
        return (title + (" —— " + snippet if snippet else ""))
    except Exception:
        return None


def lookup(text: str) -> str:
    """入口：给定一条对方消息文本，若疑似网络语/梗则联网查词义。

    返回注入用的说明文本（可直接放进 system），不需要查询时返回 None。
    """
    global _last_search_ts
    if not text or not isinstance(text, str):
        return None
    stripped = text.strip()
    if len(stripped) > 60:
        return None  # 长句不查

    # 问句提取
    term = _looks_question(stripped)
    if term is None:
        # 整句长度判断（问句形式未命中时）
        compact = _norm_text(stripped)
        if len(compact) < 2 or len(compact) > 20:
            return None
        core = compact.lower()
        if any(core == s.lower() or core.startswith(s.lower()) for s in _SKIP_SET):
            return None
        # 含较多常规字词的短句（含"你/我/他/吗"等虚词或句末语气）默认不当作梗
        if re.search(r"[你我他她它们]", core) or core.endswith(("吗", "呢", "吧", "啊")):
            # 除非它本身就是问"什么意思"（已在上方处理过）→ 保守不查
            return None
        term = stripped[:24]

    term = term.strip().strip("？?。，,！!：“”\"'")
    if len(term) < 1 or len(term) > 24:
        return None

    # 缓存
    cache = _read_cache()
    hit = cache.get(term)
    if hit and time.time() - hit.get("ts", 0) < CACHE_HOURS * 3600:
        if hit.get("text"):
            return f"【网络用语参考】网上关于「{term}」查到：{hit['text']}（供参考，若与本群实际含义不符请忽略）"
        return None

    # 限流：距离上次搜索不足 15 秒就不查
    with _lock:
        now = time.time()
        if now - _last_search_ts < _MIN_INTERVAL:
            return None
        _last_search_ts = now

    result = _search_bing(term)
    # 写缓存（失败也缓存，避免反复搜无用词）
    cache[term] = {"text": result or "", "ts": time.time()}
    if len(cache) > CACHE_MAX:
        # 只保留最新 CACHE_MAX 条
        for k in sorted(cache, key=lambda x: cache[x].get("ts", 0))[: len(cache) - CACHE_MAX]:
            cache.pop(k, None)
    _write_cache(cache)

    if result:
        return f"【网络用语参考】网上关于「{term}」查到：{result}（供参考，若与本群实际含义不符请忽略）"
    return None
