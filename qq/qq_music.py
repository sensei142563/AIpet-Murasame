# -*- coding: utf-8 -*-
"""
QQ 点歌 — 网易云音乐模糊搜索 → 下载转 wav → 发送为 QQ 语音(record, NapCat 自动转 silk)。

接口(免费公开)：
- 搜索: https://music.163.com/api/cloudsearch/pc?s=<kw>&type=1
- 播放外链: https://music.163.com/song/media/outer/url?id=<id>.mp3 (302 → 真实 mp3)
音频缓存: data/qq_music_cache/<songid>.wav (同名不重复下载)
"""

import os
import time
import urllib.parse

import requests

from tool.paths import data_path

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
       "Referer": "https://music.163.com/"}


def search(keyword, limit=5):
    """网易云模糊搜索 → [{name, artists, id, dur}]"""
    out = []
    try:
        url = ("https://music.163.com/api/cloudsearch/pc?s="
               + urllib.parse.quote(keyword) + "&type=1&limit=" + str(limit))
        r = requests.get(url, headers=_UA, timeout=10)
        songs = ((r.json().get("result") or {}).get("songs")) or []
        for v in songs[:limit]:
            arts = ",".join(a.get("name", "") for a in (v.get("artists") or []))
            out.append({"name": v.get("name", ""), "artists": arts,
                        "id": v.get("id"), "dur": int(v.get("duration", 0) or 0) / 1000})
    except Exception:
        pass
    return out


def _cache_dir():
    d = os.path.join(data_path("data"), "qq_music_cache")
    os.makedirs(d, exist_ok=True)
    return d


def download_wav(song_id, max_bytes=16 * 1024 * 1024):
    """下载 mp3(网易外链)并用 ffmpeg 转 24kHz 单声道 wav(QQ语音友好)。
    返回 wav 路径；失败返回 None。"""
    import subprocess as _sp
    if not song_id:
        return None
    out = os.path.join(_cache_dir(), f"{song_id}.wav")
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return out
    try:
        url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
        with requests.get(url, headers=_UA, timeout=20, stream=True) as r:
            if r.status_code != 200:
                return None
            total = 0
            mp3 = out + ".dl.mp3"
            with open(mp3, "wb") as f:
                for chunk in r.iter_content(65536):
                    total += len(chunk)
                    if total > max_bytes:
                        return None
                    f.write(chunk)
        if os.path.getsize(mp3) < 5000:
            try:
                os.remove(mp3)
            except Exception:
                pass
            return None
        # ffmpeg 转 24kHz 单声道 wav，并截取前 60 秒(QQ 语音单条长度限制)
        ff = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "GPT-SoVITS", "runtime", "ffmpeg.exe")
        if not os.path.exists(ff):
            ff = "ffmpeg"
        _sp.run([ff, "-y", "-i", mp3, "-t", "60", "-ar", "24000", "-ac", "1", out],
                capture_output=True, timeout=60)
        try:
            os.remove(mp3)
        except Exception:
            pass
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return out
    except Exception:
        pass
    return None
