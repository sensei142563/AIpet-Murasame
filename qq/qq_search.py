# -*- coding: utf-8 -*-
"""
QQ 自主学习工具 — 联网搜索 / 链接理解 / 图片与视频检索。

- search_web(query): 必应网页搜索 → 若干条 (标题, 摘要, URL)
- read_link(url):    打开链接抓取标题+简介（含 bilibili / 快手等视频页 og 信息）
- search_images(query): 必应图片搜索 → [{url, title}]（murl 原图）
- search_videos(query): bilibili 搜索 → [{bvid, title, author, cover, url}]
全部带超时、失败返回空结构；调用方自行静默。
"""

import re
import os
import json
import time
import urllib.parse

import requests

_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
_TIMEOUT = 8
_session = requests.Session()


def _get(url, timeout=_TIMEOUT, headers=None, referer=None):
    try:
        h = dict(_UA)
        if headers:
            h.update(headers)
        if referer:
            h["Referer"] = referer
        r = _session.get(url, headers=h, timeout=timeout)
        r.encoding = r.apparent_encoding or "utf-8"
        return r
    except Exception:
        return None


def _clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def search_web(query, num=3):
    """必应网页搜索 → [(标题, 摘要, url)]；失败返回 []"""
    import html as _html
    out = []
    try:
        url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query) + "&mkt=zh-CN"
        r = _get(url, headers={"Referer": "https://cn.bing.com/"})
        if not r:
            return out
        h = r.text
        blocks = re.findall(r'<li class="b_algo".*?(?=<li class="b_algo"|</ol>)', h, re.S)
        for b in blocks[:num]:
            m = re.search(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
            m_p = re.search(r"<p[^>]*>(.*?)</p>", b, re.S)
            if m:
                t = re.sub(r"<[^>]+>", "", m.group(2))
                out.append((_html.unescape(_clean(t)),
                            _clean(m_p.group(1) if m_p else ""),
                            m.group(1)))
    except Exception:
        pass
    return out


def _page_summary(url):
    """抓链接正文摘要 → (标题, 描述/首段, 站点)"""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        site = host.replace("www.", "").split(".")[0]
        r = _get(url, timeout=10)
        if not r:
            return "", "", site
        html = r.text
        title = ""
        mt = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
        if mt:
            title = _clean(mt.group(1))
        desc = ""
        for pat in (r'<meta[^>]+name="description"[^>]+content="([^"]*)"',
                    r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"'):
            m = re.search(pat, html, re.I)
            if m:
                desc = _clean(m.group(1))
                break
        if not desc:
            # 取正文前几段文本
            body = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
            body = _clean(body)
            # 去掉导航噪音:取 title 后一段
            idx = body.find(title[:20]) if title else -1
            desc = body[idx + len(title[:20]):idx + 400] if idx >= 0 else body[:300]
        return title, desc[:400], site
    except Exception:
        return "", "", ""


def read_link(url):
    """打开任意链接(网页/视频分享) → 一行可注入文本；失败返回 None"""
    try:
        u = url.strip()
        if not u.lower().startswith("http"):
            u = "https://" + u
        title, desc, site = _page_summary(u)
        if not title and not desc:
            return None
        parts = [f"【链接·{site}】{title}" if title else f"【链接·{site}】"]
        if desc:
            parts.append(desc)
        return "\n".join(parts)
    except Exception:
        return None


def is_link(text):
    """文本里是否含 http(s) 链接（含 b23.tv / v.kuaishou.com 等短链）"""
    return bool(re.search(r"https?://[^\s，。、；：！？（）<>一-鿿]+", text or ""))


def extract_link(text):
    m = re.search(r"https?://[^\s，。、；：！？（）<>一-鿿]+", text or "")
    return m.group(0) if m else None


def search_images(query, num=3):
    """必应图片搜索 → [{url, title}]（尽力取原图 murl）；失败返回 []"""
    out = []
    try:
        url = "https://cn.bing.com/images/search?q=" + urllib.parse.quote(query) + "&form=HDRSC2"
        r = _get(url, headers={"Referer": "https://cn.bing.com/"})
        if not r:
            return out
        html = r.text
        # murl 原图地址
        murls = re.findall(r'&quot;murl&quot;:&quot;(.*?)&quot;', html)
        if not murls:
            murls = re.findall(r'"murl":"(.*?)"', html)
        titles = re.findall(r'&quot;t&quot;:&quot;(.*?)&quot;', html) or \
            re.findall(r'"t":"(.*?)"', html)
        for i, murl in enumerate(murls[:num]):
            t = ""
            try:
                t = re.sub(r"\\u[0-9a-fA-F]{4}", "", titles[i]) if i < len(titles) else ""
            except Exception:
                pass
            out.append({"url": murl, "title": t[:80]})
    except Exception:
        pass
    return out


def _num(x) -> int:
    """把播放量/点赞数解析为整数（兼容 '1.2万'、'12,345'、int 等）"""
    try:
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x).strip().replace(",", "")
        if s.endswith("万"):
            return int(float(s[:-1]) * 10000)
        if s.endswith("亿"):
            return int(float(s[:-1]) * 100000000)
        return int(float(s))
    except Exception:
        return 0


# ══════════ B站 wbi 签名（未签名的高频请求会被风控 -799"请求过于频繁"）══════════
_WBI_CACHE = {"mixin_key": None, "ts": 0.0}
_BILI_LAST_REQ = [0.0]          # 上次 B站 API 请求时间（全局限速，防触发风控）
_SEARCH_CACHE = {}              # (类型, 关键词) -> (时间, 结果列表)，10 分钟复用

_WBI_MIXIN_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52]


def _wbi_mixin_key():
    """获取 wbi 签名用 mixin_key（缓存 1 小时）"""
    now = time.time()
    if _WBI_CACHE["mixin_key"] and now - _WBI_CACHE["ts"] < 3600:
        return _WBI_CACHE["mixin_key"]
    r = _get("https://api.bilibili.com/x/web-interface/nav",
             headers={"Referer": "https://www.bilibili.com/"})
    if not r:
        return None
    try:
        wbi = (r.json().get("data") or {}).get("wbi_img") or {}
        img_key = os.path.splitext(os.path.basename(wbi.get("img_url") or ""))[0]
        sub_key = os.path.splitext(os.path.basename(wbi.get("sub_url") or ""))[0]
        if not img_key or not sub_key:
            return None
        raw = img_key + sub_key
        mixin = "".join(raw[i] for i in _WBI_MIXIN_TAB if i < len(raw))[:32]
        _WBI_CACHE.update({"mixin_key": mixin, "ts": now})
        return mixin
    except Exception:
        return None


def _bili_get(url, params: dict, referer="https://www.bilibili.com/"):
    """带 wbi 签名 + 全局限速的 B站 API 请求（返回 json dict；失败/风控返回 None）"""
    import hashlib
    import random as _rnd
    try:
        # 全局限速：两次 B站 请求至少间隔 1.2 秒（防 -799 风控）
        gap = time.time() - _BILI_LAST_REQ[0]
        if gap < 1.2:
            time.sleep(1.2 - gap + _rnd.uniform(0, 0.3))
        _BILI_LAST_REQ[0] = time.time()
        p = dict(params)
        mk = _wbi_mixin_key()
        if mk:
            p["wts"] = int(time.time())
            items = sorted((k, str(v).translate(str.maketrans("", "", "!'()*")))
                           for k, v in p.items())
            q = urllib.parse.urlencode(items)
            p["w_rid"] = hashlib.md5((q + mk).encode()).hexdigest()
        r = _get(url + "?" + urllib.parse.urlencode(p),
                 headers={"Referer": referer}, timeout=10)
        if not r:
            return None
        j = r.json()
        if j.get("code") == -799:
            print("[QQSearch] ⚠ B站限流(-799)，请稍后再试")
            return None
        return j
    except Exception:
        return None


def _rel_score(query: str, title: str) -> int:
    """标题与搜索词的相关性粗评：2=含完整关键词；1=含关键词片段；0=不相关"""
    q = (query or "").strip().lower()
    t = (title or "").lower()
    if not q or not t:
        return 0
    if q in t:
        return 2
    kws = [k for k in re.split(r"[\s,，、]+", q) if len(k) >= 2]
    if any(k in t for k in kws):
        return 1
    # 中文无空格：用 2-gram 覆盖率兜底（如"幻域对决"→ 幻域/域对/对决）
    if len(q) >= 3:
        grams = {q[i:i + 2] for i in range(len(q) - 1)}
        hit = sum(1 for g in grams if g in t)
        if hit >= max(1, len(grams) // 3):
            return 1
    return 0


def _videos_from_results(results, query, num):
    """B站搜索结果 → 视频列表；按「相关性优先，其次播放量/点赞」排序"""
    out = []
    for v in results or []:
        if not isinstance(v, dict) or not v.get("bvid"):
            continue
        title = (v.get("title") or "").replace('<em class="keyword">', "").replace("</em>", "")
        out.append({
            "bvid": v.get("bvid", ""),
            "title": title,
            "author": v.get("author", ""),
            "play": _num(v.get("play", 0)),
            "like": _num(v.get("like", 0)),
            "cover": v.get("pic", ""),
            "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
            "rel": _rel_score(query, title),
        })
    # 相关性优先（相关的高热视频排最前），其次热度
    out.sort(key=lambda x: (-x["rel"], -x["play"], -x["like"]))
    return out[:num]


def search_videos(query, num=20):
    """bilibili 搜索视频（相关性 + 热度优先）→ [{bvid,title,author,play,like,cover,url}]
    - 综合排序(totalrank)拉取候选，保证相关性；再按「相关性→播放量→点赞」复排；
    - wbi 签名 + 全局限速 + 结果缓存 10 分钟（防 B站 -799 风控导致"搜不出来"）；
    - 失败返回 []。"""
    key = ("video", str(query))
    now = time.time()
    cached = _SEARCH_CACHE.get(key)
    if cached and now - cached[0] < 600:
        return cached[1]
    j = _bili_get("https://api.bilibili.com/x/web-interface/wbi/search/type",
                  {"search_type": "video", "keyword": query, "order": "totalrank"})
    out = []
    if j:
        out = _videos_from_results(((j.get("data") or {}).get("result")) or [], query, num)
        if not out:
            # 综合排序无结果 → 用播放量排序再试一次
            j2 = _bili_get("https://api.bilibili.com/x/web-interface/wbi/search/type",
                           {"search_type": "video", "keyword": query, "order": "click"})
            if j2:
                out = _videos_from_results(((j2.get("data") or {}).get("result")) or [], query, num)
    if out:
        _SEARCH_CACHE[key] = (now, out)
        # 缓存裁剪
        if len(_SEARCH_CACHE) > 60:
            for k in sorted(_SEARCH_CACHE, key=lambda x: _SEARCH_CACHE[x][0])[:20]:
                _SEARCH_CACHE.pop(k, None)
    return out


def search_user(name, limit=3):
    """B站用户搜索 → [{mid, uname, fans, sign}]；失败返回 []"""
    key = ("user", str(name))
    now = time.time()
    cached = _SEARCH_CACHE.get(key)
    if cached and now - cached[0] < 600:
        return cached[1]
    j = _bili_get("https://api.bilibili.com/x/web-interface/wbi/search/type",
                  {"search_type": "bili_user", "keyword": name})
    out = []
    try:
        for u in ((j.get("data") or {}).get("result")) or []:
            if not isinstance(u, dict) or not u.get("mid"):
                continue
            out.append({
                "mid": u.get("mid"),
                "uname": _clean(u.get("uname") or ""),
                "fans": _num(u.get("fans", 0)),
                "sign": _clean(u.get("usign") or u.get("sign") or "")[:40],
            })
    except Exception:
        pass
    out.sort(key=lambda x: -x["fans"])
    out = out[:limit]
    if out:
        _SEARCH_CACHE[key] = (now, out)
    return out


def user_videos(mid, num=20):
    """某 UP 主的视频列表（播放量优先）→ 与 search_videos 同结构；失败返回 []"""
    key = ("uservid", str(mid))
    now = time.time()
    cached = _SEARCH_CACHE.get(key)
    if cached and now - cached[0] < 600:
        return cached[1]
    j = _bili_get("https://api.bilibili.com/x/space/wbi/arc/search",
                  {"mid": mid, "ps": max(20, num), "pn": 1, "order": "click"},
                  referer=f"https://space.bilibili.com/{mid}")
    out = []
    try:
        vlist = (((j.get("data") or {}).get("list") or {}).get("vlist")) or []
        for v in vlist:
            if not isinstance(v, dict) or not v.get("bvid"):
                continue
            out.append({
                "bvid": v.get("bvid", ""),
                "title": _clean(v.get("title") or ""),
                "author": v.get("author", ""),
                "play": _num(v.get("play", 0)),
                "like": 0,
                "cover": v.get("pic", ""),
                "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
                "rel": 2,  # 都是该 UP 主的作品，视为相关
            })
    except Exception:
        pass
    out.sort(key=lambda x: -x["play"])
    out = out[:num]
    if out:
        _SEARCH_CACHE[key] = (now, out)
    return out


def query_trigger(text) -> bool:
    """粗略判断是否在要求搜索/查资料/想搞懂什么（供对话注入）"""
    t = text or ""
    if is_link(t):
        return True
    for w in ("搜索", "搜一下", "查一下", "上网查", "百度", "谷歌", "不知道",
              "不认识", "不了解", "不懂", "查查", "搜搜", "怎么搜", "帮我查", "帮我搜",
              "什么意思", "是什么", "啥意思", "什么梗", "如何", "怎么做", "怎么弄",
              "为什么", "为啥", "出自", "出处", "来源", "典故", "科普", "原理",
              "是谁", "怎么分辨", "区别是什么", "介绍下", "讲讲", "给我讲讲"):
        if w in t:
            return True
    return False


def note_for_text(user_text, img_desc=""):
    """根据提问文本(可选附图片描述)返回联网参考附注；不适用返回 None"""
    try:
        if not query_trigger(user_text):
            return None
        link = extract_link(user_text)
        if link:
            info = read_link(link)
            if info:
                return f"【链接内容】{info}"
        # 图片不认识 → 用识别描述词去搜
        query = (img_desc or "").strip()
        q = query if (query and not user_text.strip()) else user_text.strip()
        if not q:
            return None
        q = q[:60]
        # 查询清洗：去标点/语气词开头，搜索词更精准，结果更相关
        q = re.sub(r"[?？!！。，,、：:；;]+", " ", q).strip()
        q = re.sub(r"^(?:请问|帮我|请问一下|你好|那个|这个|就是|然后|咦|诶)\s*", "", q).strip()
        if len(q) < 2:
            return None
        res = search_web(q, num=4)
        if not res:
            return None
        lines = []
        for t, d, u in res:
            lines.append(f"{t}：{d[:200]}" if d else t)
        # 引导语让模型把资料转成自然回答（此前只堆砌标题摘要，回答生硬、像复读机）
        return ("【网络资料】以下是刚从网上查到的参考资料：\n" + "\n".join(lines) +
                "\n要求：结合资料用你自己的话自然回答对方的问题，不要逐字复述资料，"
                "也不要提「根据网络/搜索结果显示」这类话；资料与问题无关时忽略，按你已知的回答。")
    except Exception:
        return None
