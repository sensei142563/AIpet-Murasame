# -*- coding: utf-8 -*-
"""实时天气查询工具 — 供桌宠/QQ/微信各对话链路注入事实，避免模型对
"今天天气怎么样"这类问题含糊其辞或凭空编造。

数据源（全部免费、无需 API Key）：
- 城市定位：优先 config.json 顶层 weather_city（支持中文/拼音城市名，
  或 "纬度,经度" 坐标）；留空时用 ip-api.com 按出口 IP 自动定位。
- 城市名→坐标：Open-Meteo Geocoding API（支持中文）。
- 天气数据：Open-Meteo Forecast API（实时温度/体感/湿度/风/天气代码）。

可靠性设计：
- 每次 HTTP 均带 6 秒超时；失败一律静默返回 None，不影响对话主流程。
- 结果在进程内缓存 30 分钟，避免反复追问时重复请求。
"""

import os
import sys
import time

import requests

# ── Open-Meteo WMO 天气代码 → 中文 ───────────────────────────
_WMO_WORDS = {
    0: "晴", 1: "基本晴朗", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷暴伴冰雹",
}

# 16 方位（风向角度 → 中文）
_WIND_DIRS = [
    "北风", "北东北风", "东北风", "东东北风", "东风", "东东南风", "东南风",
    "南东南风", "南风", "南西南风", "西南风", "西西南风", "西风",
    "西西北风", "西北风", "北西北风",
]


def _wmo_word(code: int) -> str:
    try:
        return _WMO_WORDS.get(int(code), "天气多变")
    except Exception:
        return "天气多变"


def _wind_dir_cn(deg) -> str:
    """风向角度（0=北）→ 中文 16 方位"""
    try:
        deg = float(deg) % 360
        return _WIND_DIRS[int((deg + 11.25) // 22.5) % 16]
    except Exception:
        return "微风"


def _wind_level_cn(kmh) -> str:
    """蒲福风级（用 km/h 近似）"""
    try:
        v = float(kmh)
    except Exception:
        return "微风"
    if v < 1:
        return "0级"
    if v < 6:
        return "1级"
    if v < 12:
        return "2级"
    if v < 20:
        return "3级"
    if v < 29:
        return "4级"
    if v < 39:
        return "5级"
    if v < 50:
        return "6级"
    if v < 62:
        return "7级"
    if v < 75:
        return "8级"
    if v < 89:
        return "9级"
    if v < 103:
        return "10级"
    if v < 118:
        return "11级"
    return "12级以上"


# ── 配置与路径 ──────────────────────────────────────────────
def _app_base_dir() -> str:
    """程序根目录：frozen 用 exe 目录；源码用项目根（与 colors.py 一致）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_cfg() -> dict:
    try:
        with open(os.path.join(_app_base_dir(), "config.json"), "r",
                  encoding="utf-8") as f:
            import json
            return json.load(f)
    except Exception:
        return {}


def weather_city() -> str:
    """config.json 顶层 weather_city（空串=按 IP 自动定位）"""
    return str(_read_cfg().get("weather_city", "") or "").strip()


def weather_enabled() -> bool:
    try:
        return str(_read_cfg().get("weather_enable", "true")).lower() != "false"
    except Exception:
        return True


# ── 网络层（统一超时+静默失败） ─────────────────────────────
_TIMEOUT = 6
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIpet/1.x"}


def _get_json(url: str):
    try:
        resp = requests.get(url, headers=_UA, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _locate_by_ip():
    """按出口 IP 定位 → (中文城市, 省份, lat, lon)；失败 None"""
    j = _get_json("http://ip-api.com/json/?lang=zh-CN&fields=status,city,regionName,lat,lon")
    if not j or j.get("status") != "success":
        return None
    return (j.get("city") or "未知城市",
            j.get("regionName") or "",
            j.get("lat"), j.get("lon"))


def _geocode(name: str):
    """中文/拼音城市名 → (显示名, 省份, lat, lon)；失败 None"""
    import urllib.parse as _up
    url = ("https://geocoding-api.open-meteo.com/v1/search?name="
           + _up.quote(name) + "&count=1&language=zh&format=json")
    j = _get_json(url)
    results = (j or {}).get("results") or []
    if not results:
        return None
    r = results[0]
    return (r.get("name") or name,
            r.get("admin1") or "",
            r.get("latitude"), r.get("longitude"))


def _resolve_location():
    """返回 (显示城市, 区域, lat, lon)；任何失败返回 None"""
    cfg_city = weather_city()
    if cfg_city:
        # 支持直接填 "纬度,经度"
        if "," in cfg_city:
            try:
                lat, lon = cfg_city.split(",", 1)
                return cfg_city, "", float(lat), float(lon)
            except Exception:
                return None
        geo = _geocode(cfg_city)
        if geo and geo[2] is not None and geo[3] is not None:
            return geo
        # 地理编码失败 → 退回自动定位
        return _locate_by_ip()
    return _locate_by_ip()


# ── 主查询（带 30 分钟缓存） ────────────────────────────────
_CACHE: dict = {"key": None, "ts": 0.0, "note": None}
_CACHE_TTL = 30 * 60


def get_weather_note() -> str | None:
    """查询当前天气，返回一行中文摘要（形如
    「【实时天气】南京（江苏）现在 24°C，多云；体感 26°C，湿度 77%；东北风2级，数据更新于 21:00」）。
    任何失败（网络/定位/解析）返回 None，调用方静默跳过。"""
    loc = _resolve_location()
    if not loc:
        return None
    city, region, lat, lon = loc

    cache_key = f"{city}|{lat},{lon}"
    if _CACHE["key"] == cache_key and time.time() - _CACHE["ts"] < _CACHE_TTL:
        return _CACHE["note"]

    try:
        url = ("https://api.open-meteo.com/v1/forecast?latitude="
               f"{lat}&longitude={lon}&timezone=auto&current="
               "temperature_2m,relative_humidity_2m,apparent_temperature,"
               "weather_code,wind_speed_10m,wind_direction_10m")
        j = _get_json(url)
        cur = (j or {}).get("current") or {}
        if not cur or cur.get("temperature_2m") is None:
            return None

        temp = round(float(cur["temperature_2m"]))
        feels = round(float(cur.get("apparent_temperature") or cur["temperature_2m"]))
        hum = int(cur.get("relative_humidity_2m") or 0)
        word = _wmo_word(cur.get("weather_code"))
        wind = f"{_wind_dir_cn(cur.get('wind_direction_10m'))}{_wind_level_cn(cur.get('wind_speed_10m'))}"
        when = str(cur.get("time") or "")[11:16] or "刚刚"

        region_txt = f"（{region}）" if region and region != city else ""
        note = (f"【实时天气】{city}{region_txt}现在 {temp}°C，{word}；"
                f"体感 {feels}°C，湿度 {hum}%；{wind}，数据更新于 {when}。")
        _CACHE.update({"key": cache_key, "ts": time.time(), "note": note})
        return note
    except Exception:
        return None


# ── 提问意图识别 ────────────────────────────────────────────
_WEATHER_HINT_WORDS = (
    "天气", "气温", "温度", "多少度", "几度", "摄氏度", "下雪", "下雨",
    "大雨", "暴雨", "阵雨", "雷阵雨", "刮风", "风大", "风力", "风速",
    "湿度", "闷热", "带伞", "防晒", "晴天", "阴天", "冷暖", "暖和",
    "凉快", "冷不冷", "热不热", "冷吗", "热吗", "好冷", "好热", "真冷",
    "真热", "好闷", "下雪了", "下雨了", "天气如何", "天怎么样", "雪下得",
)


def weather_mentioned(text: str) -> bool:
    """粗略判断一句话是否在问天气/气温（命中即触发天气注入，宁多勿漏）"""
    if not text:
        return False
    return any(w in text for w in _WEATHER_HINT_WORDS)


def weather_note_if_asked(text: str) -> str | None:
    """命中天气提问 → 返回天气摘要（供注入 system/前缀）；否则 None"""
    try:
        if not weather_enabled() or not weather_mentioned(text):
            return None
        return get_weather_note()
    except Exception:
        return None
