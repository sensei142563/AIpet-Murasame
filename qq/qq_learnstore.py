# -*- coding: utf-8 -*-
"""
自主学习知识库（本机存储，仅作回答参考素材）：
- media : 学到的群图片/视频内容描述（近期 40 条）
- links : 学到的链接内容（标题+简介，近期 40 条）
- chats : 各群近期对话文本（每群 20 条，学习话题与说话风格）
检索 retrieve(text, gid)：按关键词交集返回相关注文，供对话注入。
"""

import os
import json
import time
import threading

from tool.paths import data_path

_lock = threading.Lock()
_CAP_MEDIA = 40
_CAP_LINKS = 40
_CAP_CHAT = 20
_STATE = None
_PATH = None


def _ensure():
    global _STATE, _PATH
    if _STATE is None:
        _PATH = os.path.join(data_path("data"), "qq_learnstore.json")
        try:
            if os.path.exists(_PATH):
                with open(_PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
                _STATE = {"media": d.get("media", []), "links": d.get("links", []),
                          "chats": d.get("chats", {})}
            else:
                _STATE = {"media": [], "links": [], "chats": {}}
        except Exception:
            _STATE = {"media": [], "links": [], "chats": {}}
    return _STATE


def _save():
    try:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(_STATE, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def add_media(group, who, kind, desc):
    """记录学到的一条图片/视频内容"""
    with _lock:
        st = _ensure()
        st["media"].append({"t": time.time(), "group": str(group),
                            "who": who or "", "kind": kind, "desc": (desc or "")[:300]})
        st["media"] = st["media"][-_CAP_MEDIA:]
        _save()


def add_link(group, who, title, url, desc=""):
    with _lock:
        st = _ensure()
        st["links"].append({"t": time.time(), "group": str(group), "who": who or "",
                            "title": (title or "")[:120], "url": (url or "")[:300],
                            "desc": (desc or "")[:200]})
        st["links"] = st["links"][-_CAP_LINKS:]
        _save()


def add_chat(group, who, text):
    """记录一条群聊文本（学习话题/风格）"""
    with _lock:
        st = _ensure()
        gid = str(group)
        items = st["chats"].setdefault(gid, [])
        items.append({"t": time.time(), "who": who or "", "text": (text or "")[:200]})
        st["chats"][gid] = items[-_CAP_CHAT:]
        _save()


_STOP = set("的一是在不了有和人这中大为上你个地小我等你要他会对就都说也得你去里看过们")


def _keywords(text):
    """简单中文关键词：去掉停用字后的 2~4 字片段"""
    t = (text or "")
    t = t.replace(" ", "").replace("？", "").replace("?", "").replace("。", "")
    t = t.replace("吗", "").replace("呢", "").replace("啊", "").replace("呀", "")
    if not t:
        return []
    out = []
    n = len(t)
    for i in range(n):
        for L in (4, 3, 2):
            if i + L <= n:
                w = t[i:i + L]
                if any(ch in _STOP for ch in w):
                    continue
                out.append(w)
    return out


def retrieve(text, gid=None, max_note=3, window=3600 * 24):
    """从学习库检索与提问相关的近期内容 → 注文行列表（最多 max_note）"""
    kws = _keywords(text)
    if not kws:
        return []
    kws = kws[:12]
    out = []
    try:
        with _lock:
            st = _ensure()
            now = time.time()
            candidates = []
            for m in st["media"]:
                if now - m.get("t", 0) > window:
                    continue
                if gid and str(m.get("group")) != str(gid):
                    continue
                score = sum(1 for k in kws if k in m.get("desc", ""))
                if score:
                    candidates.append((score, m.get("t", 0),
                                       f"[学过的{'图' if m.get('kind') == 'image' else '视频'}] {m.get('desc', '')[:120]}"))
            for m in st["links"]:
                if now - m.get("t", 0) > window * 2:
                    continue
                if gid and str(m.get("group")) != str(gid):
                    continue
                score = sum(1 for k in kws if k in m.get("title", "") or k in m.get("desc", ""))
                if score:
                    candidates.append((score, m.get("t", 0),
                                       f"[学过的链接] {m.get('title', '')[:60]}（{m.get('url', '')[:90]}）"))
            if gid:
                for m in st["chats"].get(str(gid), []):
                    if now - m.get("t", 0) > window:
                        continue
                    score = sum(1 for k in kws if k in m.get("text", ""))
                    if score >= 2:
                        candidates.append((score, m.get("t", 0),
                                           f"[群里之前聊到] {m.get('who', '')}：{m.get('text', '')[:120]}"))
            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
            for _, _, line in candidates[:max_note]:
                if line not in out:
                    out.append(line)
    except Exception:
        pass
    return out
