# -*- coding: utf-8 -*-
"""联网搜索：她可以上网查东西（参考 HealthMate 的 Knowledge Agent）。

实测（这台机器）：
    cn.bing.com  ✅ 0.3 秒返回、有结果   ← 首选
    baidu.com    ✅ 1.2 秒返回           ← 备用
    duckduckgo / wikipedia  ❌ 连不上（被墙）

流程（和看屏幕/看文件一个套路）：
    她输出一行「【搜索】关键词」→ 桌宠真的去搜 → 把标题+摘要交给她 →
    她用自己的话回答（结果里会带来源网址，方便她说"我是从哪儿看到的"）。

安全与礼貌：只做只读的网页搜索；结果缓存 5 分钟、两次搜索至少隔 3 秒；
只取标题与摘要，不抓正文，不发送任何本机信息。
"""
import html
import json
import os
import re
import time

SEARCH_MARK = "【搜索】"
_MARK_RE = re.compile("[【\\[]\\s*搜索\\s*[】\\]]\\s*([^\"\\]\\n]{1,80})")
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
_cache = {}                      # {query: (ts, results)}
_last_call = [0.0]
MIN_GAP = 3.0                    # 两次搜索最小间隔（秒）
CACHE_TTL = 300.0


def enabled() -> bool:
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("web_search_enabled", "true")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return True


def set_enabled(on: bool) -> bool:
    try:
        from tool.config import get_config
        import os as _os
        cfg = dict(get_config("./config.json") or {})
        cfg["web_search_enabled"] = "true" if on else "false"
        p = _os.path.join("config.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        _os.replace(tmp, p)
        print(f"[搜索] 联网搜索 → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        print(f"[搜索] ⚠ 写开关失败: {e}")
        return False


def _clean(s: str) -> str:
    s = re.sub("<[^>]+>", "", str(s or ""))
    s = html.unescape(s)
    return re.sub("\\s+", " ", s).strip()


def _parse_bing(txt: str, limit: int) -> list:
    """解析 Bing 结果。

    ⚠ 不能用 `<li class="b_algo">.*?</li>` 那种整块匹配：Bing 每条结果里还有嵌套列表，
      非贪婪匹配会在第一个 </li> 就截断，而标题（h2）往往在后面 → 一条都取不到（实测）。
      改成"按 b_algo 出现的位置切片"，每片取到下一片开始为止。
    """
    out = []
    try:
        # 每条结果里都塞了一堆内联 <link rel=stylesheet>，先去掉再解析（不然标题前面有几千字垃圾）
        txt = re.sub('<link[^>]*>', '', str(txt or ""))
        marks = [m.start() for m in re.finditer('class="b_algo"', txt)]
        for i, pos in enumerate(marks):
            end = marks[i + 1] if i + 1 < len(marks) else min(len(txt), pos + 6000)
            blk = txt[pos:end]
            a = re.search('<h2[^>]*>\\s*<a[^>]*href="(http[^"]+)"[^>]*>(.*?)</a>', blk, re.S)
            if not a:
                continue
            url, title = a.group(1), _clean(a.group(2))
            sn = re.search('<p[^>]*>(.*?)</p>', blk, re.S)
            snippet = _clean(sn.group(1)) if sn else ""
            if title:
                out.append({"title": title, "url": url, "snippet": snippet[:220]})
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


def _parse_baidu(txt: str, limit: int) -> list:
    out = []
    try:
        for m in re.finditer('<div[^>]*class="result[^"]*".*?</div>\\s*</div>', txt, re.S):
            blk = m.group(0)
            a = re.search('<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
            if not a:
                continue
            url, title = a.group(1), _clean(a.group(2))
            sn = re.search('<span[^>]*class="content-right_8Zs40"[^>]*>(.*?)</span>', blk, re.S) \
                or re.search('<div[^>]*class="c-abstract[^"]*"[^>]*>(.*?)</div>', blk, re.S)
            snippet = _clean(sn.group(1)) if sn else ""
            if title and url.startswith("http"):
                out.append({"title": title, "url": url, "snippet": snippet[:220]})
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


def _fetch(url: str, params: dict) -> str:
    import requests
    try:
        from tool.net_env import bypass_proxy_for_local
        bypass_proxy_for_local()
    except Exception:
        pass
    r = requests.get(url, params=params, headers={"User-Agent": _UA,
                                                  "Accept-Language": "zh-CN,zh;q=0.9"},
                     timeout=(4, 12), allow_redirects=True)
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text or ""


def search(query: str, limit: int = 5) -> list:
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
        out = _parse_bing(_fetch("https://cn.bing.com/search", {"q": q, "ensearch": "0"}), limit)
    except Exception as e:
        print(f"[搜索] Bing 失败: {type(e).__name__}: {e}")
    if not out:
        try:
            out = _parse_baidu(_fetch("https://www.baidu.com/s", {"wd": q}), limit)
        except Exception as e:
            print(f"[搜索] 百度也失败: {type(e).__name__}: {e}")
    _cache[q] = (time.time(), out)
    print(f"[搜索] 「{q}」→ {len(out)} 条结果")
    return out


def context_text(query: str, limit: int = 5) -> str:
    """把搜索结果拼成给模型看的一段（她说"我查到的"就有依据了）"""
    res = search(query, limit)
    if not res:
        return ""
    lines = [f"（你刚上网查了「{query}」，下面是搜到的标题与摘要，"
             f"用你自己的话讲给主人听；不确定的地方就说没查到，别编。）"]
    for i, r in enumerate(res, 1):
        lines.append(f"{i}. {r.get('title')}")
        if r.get("snippet"):
            lines.append(f"   摘要：{r.get('snippet')}")
        if r.get("url"):
            lines.append(f"   来源：{r.get('url')}")
    return chr(10).join(lines)


def parse(text: str) -> list:
    """从回复里解析【搜索】标记 → [关键词]"""
    out = []
    for m in _MARK_RE.finditer(str(text or "")):
        q = str(m.group(1)).strip("：:，,。\"'「」")
        if q:
            out.append(q)
    return out[:2]


def clean_for_speech(text: str) -> str:
    src = str(text or "")
    try:
        if not _MARK_RE.search(src):
            return src
        return re.sub("\\n{2,}", chr(10), _MARK_RE.sub("", src)).strip()
    except Exception:
        return src


def prompt_rules() -> str:
    if not enabled():
        return ""
    return (
        "【联网搜索（已开启）】遇到你不确定的事、或主人问「最新 / 今天 / 多少钱 / 是谁」这类"
        "需要外面信息的问题，就上网查一下。写一行：\n"
        "【搜索】关键词（例如【搜索】今天北京天气 / 【搜索】DeepSeek 最新公告）\n"
        "★ 那一行不会被念出来；桌宠会真的去搜，把结果交给你，你再用自己的话讲给主人听。\n"
        "★ 查不到就老实说没查到，别编。"
    )


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("开关:", enabled())
    print("规则:", prompt_rules().splitlines()[0][:50])
    print("解析:", parse("好，我查查。【搜索】今天北京天气"))
    print()
    for q in ("人工智能 桌宠", "DeepSeek 公司"):
        t0 = time.time()
        res = search(q, limit=3)
        print(f"=== 「{q}」（{time.time() - t0:.1f}s，{len(res)} 条）===")
        for r in res:
            print("  ·", r["title"][:50])
            print("    ", (r.get("snippet") or "")[:70])
            print("    ", r["url"][:70])
        print()
