# -*- coding: utf-8 -*-
"""联网搜索：主人问「最新／今天／多少钱／是谁」这类需要外面信息的问题时，她先上网查一眼。

和本仓库其它"看一眼"能力的关系
------------------------------
`tool/screen_intent.py`（看屏幕）是**调用前**判断意图 → 抓屏识别 → 把内容并进这一轮提问；
联网搜索走同一套路：**调用前**判断主人是不是在问需要外部信息的事 → 搜 → 把标题/摘要
并进这一轮。这样只**多走一次网络请求**，不动她的句子流水线。

⚠ 与对端实现的差别（有意为之）：对端是"她写一行【搜索】关键词 → 桌宠搜 → 结果交回她 →
  她再答一轮"，那需要**二次对话**（他们的句子流水线支持）。我们这边单趟回答，所以不往
  提示词里宣传标记 —— 宣传了却没人执行，等于骗模型。`parse()` / `clean_for_speech()`
  仍然保留：万一她照着旧习惯写了标记，那一行至少不会被念出来。

礼貌与安全：只读搜索；结果缓存 5 分钟、两次搜索至少隔 3 秒；只取标题与摘要，不抓正文，
不发送任何本机信息。
"""
import html
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(APP, "config.json")

SEARCH_MARK = "【搜索】"
_MARK_RE = re.compile("[【\\[]\\s*搜索\\s*[】\\]]\\s*([^\"\\]\\n]{1,80})")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
MIN_GAP = 3.0                    # 两次搜索最小间隔（秒）
CACHE_TTL = 300.0                # 结果缓存 5 分钟
DEFAULT_LIMIT = 5

# 明确要求去查的动词（命中就搜）
_VERBS = ("查一下", "查查", "搜一下", "搜搜", "搜索一下", "帮我查", "帮我搜",
          "上网查", "联网查", "百度一下", "google 一下")
# 这些词说明答案在"外面"（不需要动词也搜）
_ASK = ("最新", "多少钱", "什么价格", "价格", "是谁", "什么时候", "有没有", "新闻",
        "天气", "汇率", "股价", "油价", "官网", "下载地址", "版本号", "排名", "推荐",
        "怎么样", "怎么用", "是什么")
# 明确不要查（省一次请求，也尊重主人）
_NO = ("不用查", "不用搜", "别搜", "别查", "不要搜", "我自己查")
# 客气话/口头禅，搜之前去掉（留着会把关键词冲淡）
_FILLER = ("帮我", "请问", "麻烦", "你能", "能不能", "可以", "帮忙", "给我")

_cache = {}                      # {query: (ts, results)}
_last_call = [0.0]


def _cfg() -> dict:
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def enabled() -> bool:
    try:
        from tool.config import as_bool
        return as_bool(_cfg().get("web_search_enabled", "true"), True)
    except Exception:
        return True


def set_enabled(on: bool) -> bool:
    """写开关。⚠ 只改这一个键（走 tool.config.set_key），别整份 dump（会拿示例占位值落盘）"""
    try:
        from tool.config import set_key
        ok = bool(set_key(CFG_PATH, "web_search_enabled", "true" if on else "false"))
        if ok:
            print("[搜索] 联网搜索 → %s" % ("已开启" if on else "已关闭"))
        return ok
    except Exception as e:
        print("[搜索] ⚠ 写开关失败: %s" % e)
        return False


def needs_search(text: str) -> str:
    """主人在问需要外面信息的事吗？返回要搜的关键词（"" = 不用搜）。

    为什么用"关键词+动词"这种朴素判据、而不是再调一次模型：这条路每问一句都要走，
      多一次模型调用既慢又费；而且判错最多是多搜一次（有 3 秒间隔与 5 分钟缓存兜着）。
    """
    t = str(text or "").strip()
    if not t or len(t) > 120:
        return ""
    low = t.lower()
    for w in _NO:
        if w in t:
            return ""
    q, hit = t, False
    for v in _VERBS:
        if v in t or v.lower() in low:
            q = q.replace(v, " ")
            hit = True
    if not hit and not any(w in t for w in _ASK):
        return ""
    for w in _FILLER:
        q = q.replace(w, " ")
    q = re.sub(r"[\s　]+", " ", q)
    q = q.strip(" 　：:，,。！!？?、~～\"'「」")
    if len(q) < 2:
        return ""
    return q[:60]


def _clean(s) -> str:
    """HTML 片段 → 纯文字（去标签、还原实体、压空白）"""
    s = re.sub("<[^>]+>", "", str(s or ""))
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_bing(txt: str, limit: int = DEFAULT_LIMIT) -> list:
    """解析 Bing 结果页 → [{"title","url","snippet"}]。

    ⚠ 不能用 `<li class="b_algo">.*?</li>` 那种整块匹配：每条结果里还有嵌套列表，
      非贪婪会在第一个 </li> 就截断，而标题（h2）往往在后面 → 一条都取不到（实测）。
      改成"按 b_algo 出现的位置切片"，每片取到下一片开始为止。
    """
    out = []
    try:
        # 每条结果里塞了一堆内联 <link rel=stylesheet>，先去掉（不然标题前面挂着几千字垃圾）
        txt = re.sub("<link[^>]*>", "", str(txt or ""))
        marks = [m.start() for m in re.finditer('class="b_algo"', txt)]
        for i, pos in enumerate(marks):
            end = marks[i + 1] if i + 1 < len(marks) else min(len(txt), pos + 6000)
            blk = txt[pos:end]
            a = re.search('<h2[^>]*>\\s*<a[^>]*href="(http[^"]+)"[^>]*>(.*?)</a>', blk, re.S)
            if not a:
                continue
            url, title = a.group(1), _clean(a.group(2))
            sn = re.search("<p[^>]*>(.*?)</p>", blk, re.S)
            snippet = _clean(sn.group(1)) if sn else ""
            if title:
                out.append({"title": title, "url": url, "snippet": snippet[:220]})
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


def parse_baidu(txt: str, limit: int = DEFAULT_LIMIT) -> list:
    """解析百度结果页（备用；百度 class 名会变，所以两条摘要正则都试）"""
    out = []
    try:
        for m in re.finditer('<div[^>]*class="result[^"]*".*?</div>\\s*</div>', txt, re.S):
            blk = m.group(0)
            a = re.search('<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
            if not a:
                continue
            url, title = a.group(1), _clean(a.group(2))
            sn = (re.search('<span[^>]*class="content-right_[^"]*"[^>]*>(.*?)</span>', blk, re.S)
                  or re.search('<div[^>]*class="c-abstract[^"]*"[^>]*>(.*?)</div>', blk, re.S))
            snippet = _clean(sn.group(1)) if sn else ""
            if title and url.startswith("http"):
                out.append({"title": title, "url": url, "snippet": snippet[:220]})
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


def _fetch(url: str, params: dict) -> str:
    """取一个结果页（只读；超时短，失败由调用方回落下一个引擎）"""
    import requests
    try:
        from tool.net_env import bypass_proxy_for_local
        bypass_proxy_for_local()
    except Exception:
        pass
    r = requests.get(url, params=params,
                     headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                     timeout=(4, 12), allow_redirects=True)
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text or ""


def search(query: str, limit: int = DEFAULT_LIMIT) -> list:
    """搜网页 → [{"title","url","snippet"}]（Bing 优先，百度备用）"""
    q = str(query or "").strip()[:60]
    if not q or not enabled():
        return []
    now = time.time()
    hit = _cache.get(q)
    if hit and now - float(hit[0]) < CACHE_TTL:
        return list(hit[1])[:limit]
    gap = now - float(_last_call[0] or 0)
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _last_call[0] = time.time()
    out = []
    try:
        out = parse_bing(_fetch("https://cn.bing.com/search", {"q": q, "ensearch": "0"}), limit)
    except Exception as e:
        print("[搜索] Bing 失败: %s: %s" % (type(e).__name__, e))
    if not out:
        try:
            out = parse_baidu(_fetch("https://www.baidu.com/s", {"wd": q}), limit)
        except Exception as e:
            print("[搜索] 百度也失败: %s: %s" % (type(e).__name__, e))
    _cache[q] = (time.time(), out)
    print("[搜索] 「%s」→ %d 条结果" % (q, len(out)))
    return out


def context_text(query: str, limit: int = DEFAULT_LIMIT) -> str:
    """把搜索结果拼成给模型看的一段（她说"我查到的"就有依据了；查不到就返回空串）"""
    res = search(query, limit)
    if not res:
        return ""
    lines = ["（你刚上网查了「%s」，下面是搜到的标题与摘要。用你自己的话讲给主人听；"
             "不确定或搜不到的地方就说没查到，别编。带上网址来源。）" % query]
    for i, r in enumerate(res, 1):
        lines.append("%d. %s" % (i, r.get("title")))
        if r.get("snippet"):
            lines.append("   摘要：%s" % r.get("snippet"))
        if r.get("url"):
            lines.append("   来源：%s" % r.get("url"))
    return "\n".join(lines)


def parse(text: str) -> list:
    """从回复里解析【搜索】标记 → [关键词]（**保留但不再向模型宣传**，见模块开头说明）"""
    out = []
    for m in _MARK_RE.finditer(str(text or "")):
        q = str(m.group(1)).strip("：:，,。\"'「」")
        if q:
            out.append(q)
    return out[:2]


def clean_for_speech(text: str) -> str:
    """万一她写了【搜索】标记，那一行不念出来"""
    src = str(text or "")
    try:
        if not _MARK_RE.search(src):
            return src
        return re.sub("\\n{2,}", "\n", _MARK_RE.sub("", src)).strip()
    except Exception:
        return src


def summary_text() -> str:
    return "联网搜索：%s（问「最新/今天/多少钱/是谁」这类问题时才会查）" % (
        "开着" if enabled() else "关着")


if __name__ == "__main__":
    # 手动体检：python -m tool.web_search        → 只看判断，**不联网**
    #           python -m tool.web_search --live → 真搜两个词看看
    print(summary_text())
    for t in ("帮我查一下 DeepSeek 最新公告", "今天天气怎么样？", "我们聊聊天吧",
              "不用查了，我知道了"):
        print("  %-26s → %r" % (t, needs_search(t)))
    print("解析:", parse("我查查。【搜索】今天北京天气"))
    print("去掉标记:", repr(clean_for_speech("我查查。\n【搜索】今天北京天气")))
    if "--live" in sys.argv:
        for q in ("DeepSeek 公司", "人工智能 桌宠"):
            t0 = time.time()
            res = search(q, limit=3)
            print("=== 「%s」（%.1fs，%d 条）===" % (q, time.time() - t0, len(res)))
            for r in res:
                print("  ·", r["title"][:50])
                print("    ", (r.get("snippet") or "")[:70])
                print("    ", r["url"][:70])
