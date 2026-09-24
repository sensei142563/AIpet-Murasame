# -*- coding: utf-8 -*-
"""
QQ 配置模块 — 读取 config.json 中的 qq_* 配置项。
"""

import os
import json
import socket

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# 表情包根目录 — 按当前角色动态解析（不再固定根目录）
# 由 pet_registry.get_sticker_dir() 返回角色包内的 biaoqingbao/（若无则返回空 → QQ 不发图）
from pets.pet_registry import get_sticker_dir
STICKER_DIR = get_sticker_dir()
if not STICKER_DIR:
    STICKER_DIR = os.path.join(BASE_DIR, "biaoqingbao")  # 兜底旧路径

# F5-TTS 服务端口（长文本中文语音合成）
F5TTS_PORT = 9881


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check_port_open(port, host="127.0.0.1", timeout=1):
    """检查本机端口是否可连接"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def _cfg_int_min(value, default, minimum):
    """读取整数配置：非数字/空值回退 default，再取不小于 minimum（分钟下限防呆）"""
    try:
        return max(minimum, int(float(str(value).strip())))
    except Exception:
        return max(minimum, default)


def _parse_master_ids(cfg):
    """解析主人白名单：qq_owner_id（第一位/主主人） + qq_master_ids（额外，最多 4 个）。
    总数上限 5；自动去重、过滤非法项。"""
    import re as _re
    ids = []

    def _add(v):
        s = str(v or "").strip()
        if s and s.isdigit() and s not in ids:
            ids.append(s)

    _add(cfg.get("qq_owner_id"))
    raw = cfg.get("qq_master_ids")
    if isinstance(raw, list):
        for v in raw:
            _add(v)
    elif isinstance(raw, str):
        for part in _re.split(r"[,，;；\s]+", raw):
            _add(part)
    return ids[:5]


def _is_local_url(ws_url: str) -> bool:
    """地址是否指向本机（只有本机才允许去 NapCat 目录里找 token，远端不猜）"""
    try:
        u = str(ws_url or "").lower()
        return ("127.0.0.1" in u) or ("localhost" in u) or ("[::1]" in u)
    except Exception:
        return False


def _ws_port_of(ws_url: str) -> str:
    """从 ws://host:port/path 里取端口（取不到返回空）"""
    try:
        s = str(ws_url or "")
        s = s.split("://", 1)[-1]
        s = s.split("/", 1)[0]
        if ":" in s:
            return s.rsplit(":", 1)[-1].strip()
        return "80"
    except Exception:
        return ""


def discover_ws_token(ws_url: str = "") -> str:
    """从 NapCat 自己的配置里读正向 WebSocket 的 token（仅本机地址）。

    为什么需要：NapCat 重装/重置配置时会**随机生成**新 token（写在
    NapCat/config/onebot11_<QQ号>.json 里），而 config.json 里如果没有配
    qq_napcat_token（或配的是旧值），程序握手不带鉴权头 → NapCat 先接受连接、
    再回一帧 retcode 1403 然后立刻断开（表现：连上就断、5 秒一轮重连）。
    这里按端口自动找，免去手工同步。
    """
    try:
        ws_url = ws_url or str(_load_config().get("qq_napcat_ws", "ws://127.0.0.1:3001"))
        if not _is_local_url(ws_url):
            return ""
        port = _ws_port_of(ws_url)
        # 目录定位复用 _napcat_config_dir()（原来这段是内联重复的，两处维护容易走偏）
        nc = _napcat_config_dir()
        if not os.path.isdir(nc):
            return ""
        best = ""
        for name in sorted(os.listdir(nc)):
            if not (name.startswith("onebot11_") and name.endswith(".json")):
                continue
            try:
                with open(os.path.join(nc, name), "r", encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                continue
            net = d.get("network") or {}
            for key in ("websocketServers", "websocketClients"):
                for srv in (net.get(key) or []):
                    try:
                        s_port = str(srv.get("port", "") or "").strip()
                        tok = str(srv.get("token", "") or "").strip()
                        if not tok:
                            continue
                        # 端口一致优先；没写端口时也接受（只有一个 token 的常见情况）
                        if port and s_port and s_port != port:
                            continue
                        if port and not s_port:
                            best = best or tok
                            continue
                        print(f"[QQConfig] 🔑 已从 NapCat 配置自动读取 WS token（{name}）")
                        return tok
                    except Exception:
                        continue
        return best
    except Exception as e:
        print(f"[QQConfig] ⚠ 自动读取 NapCat token 失败: {e}")
        return ""


def _napcat_config_dir() -> str:
    """定位 NapCat 自己的 config 目录（兼容几种安装布局）。找不到返回空串。"""
    cands = [os.path.join(BASE_DIR, "NapCat.Shell.Windows.OneKey", "NapCat", "config"),
             os.path.join(BASE_DIR, "NapCat.Shell.Windows.OneKey", "config"),
             os.path.join(BASE_DIR, "NapCat", "config")]
    for c in cands:
        if os.path.isdir(c):
            return c
    return ""


def discover_webui_url() -> dict:
    """从 NapCat 自己的 webui.json 读出 WebUI 地址（本机安装才有）。

    为什么需要：启动器原来把 `http://127.0.0.1:6099` **硬编码**在按钮里，还提示
    「Token 见 config.json」——但 config.json 里根本没有 WebUI token（它在
    NapCat/config/webui.json 里），端口也是 NapCat 那边可改的。用户点了只会打开一个
    登录页、不知道 token 去哪找；NapCat 没启动时更是一个死链接。

    NapCat 期望的形式是 `http://127.0.0.1:<port>/webui?token=<token>`
    （根路径 / 会 301 到 /webui；除 /auth/login 外都要求 token）。

    返回 {"url": 打开用的地址, "port": 端口, "token": token(有则非空), "source": 来源}
    """
    port, token, source = 6099, "", "默认值"
    try:
        nc = _napcat_config_dir()
        if nc:
            p = os.path.join(nc, "webui.json")
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                try:
                    _p = int(d.get("port") or 0)
                    if _p > 0:
                        port = _p
                except Exception:
                    pass
                token = str(d.get("token", "") or "").strip()
                if d.get("disableWebUI") is True:
                    source = "webui.json（ 已禁用 WebUI）"
                else:
                    source = "webui.json"
            # 退一步：用 config.json 里配的 NapCat HTTP 地址（历史上把它当 WebUI 口用过）
            if source == "默认值":
                _http = str(_load_config().get("qq_napcat_http", "") or "").strip()
                if _http and _is_local_url(_http):
                    try:
                        from urllib.parse import urlparse
                        u = urlparse(_http)
                        if u.port:
                            port = int(u.port)
                            source = "config.json qq_napcat_http"
                    except Exception:
                        pass
    except Exception as e:
        print(f"[QQConfig] ⚠ 读取 NapCat WebUI 配置失败: {e}")
    url = "http://127.0.0.1:%d/webui" % port
    if token:
        from urllib.parse import quote
        url += "?token=" + quote(token, safe="")
    return {"url": url, "port": port, "token": token, "source": source}


def get_qq_token(ws_url: str = "") -> str:
    """优先用 config.json 的 qq_napcat_token；没配就自动去 NapCat 配置里找。"""
    cfg = _load_config()
    tok = str(cfg.get("qq_napcat_token", "") or "").strip()
    if tok:
        return tok
    return discover_ws_token(ws_url or cfg.get("qq_napcat_ws", ""))


def get_qq_config():
    """读取 QQ 相关配置（带默认值）"""
    cfg = _load_config()
    f5tts_ready = check_port_open(F5TTS_PORT)
    _ws = cfg.get("qq_napcat_ws", "ws://127.0.0.1:3001")
    return {
        # NapCat WebSocket 地址（事件上报 + 调用 API 走同一连接）
        "ws_url": _ws,
        # NapCat 正向 WS token 鉴权（NapCat 开启 token 时必填，否则连上即断 retcode 1403）
        # 未配置时自动从 NapCat 的 onebot11_*.json 读取（仅本机）
        "napcat_token": get_qq_token(_ws),
        # NapCat WebUI (HTTP API，主要用于发送消息等)
        "http_url": cfg.get("qq_napcat_http", "http://127.0.0.1:6099"),
        # 是否在回复时携带表情包 gif
        "send_sticker": str(cfg.get("qq_send_sticker", "true")).lower() == "true",
        # 是否在回复时附带 F5-TTS 语音
        "send_voice": str(cfg.get("qq_send_voice", "false")).lower() == "true",
        # 是否启用图片识别（收到图片时调用视觉模型识别，模型由 vision_model_name 配置）
        "vision_enabled": str(cfg.get("qq_vision_enabled", "true")).lower() == "true",
        # 是否启用语音识别（收到语音消息时用 faster-whisper 转文字）
        "stt_enabled": str(cfg.get("qq_stt_enabled", "false")).lower() == "true",
        # 是否允许群聊（只 @ 时回复）
        "allow_groups": str(cfg.get("qq_allow_groups", "true")).lower() == "true",
        # 离线消息补拉（默认开：启动时补回离线期间消息；NapCat 不支持时可在 PCL 设置关闭。
        # 即便开启，任何请求失败/超时也已做极短超时 + 不拖断主 WS）
        "offline_enabled": str(cfg.get("qq_offline_enable", "true")).lower() == "true",
        # 空闲自动离线（默认关：保持始终活跃，不会自动离线导致不回复。
        # 开启后：空闲超过 qq_auto_offline_minutes 分钟 → QQ 状态切为「离开」并暂停自动回复；
        # 收到主人 QQ 的消息 → 立即恢复在线并正常回复）
        "auto_offline_enabled": str(cfg.get("qq_auto_offline_enable", "false")).lower() == "true",
        # 非法值（0/负数/非数字）一律回退默认并取下限 1 分钟
        "auto_offline_minutes": _cfg_int_min(cfg.get("qq_auto_offline_minutes", 30), 30, 1),
        # 活泼模式（默认关：仅在被 @ 时回复群聊。开启后：监控所在群的消息，
        # 冷却间隔后若群里有新动静，会作为角色主动接一句话活跃群气氛）
        "lively_enabled": str(cfg.get("qq_lively_enable", "false")).lower() == "true",
        # 接话间隔最低 1 分钟（UI 调节范围 1~120）；非法值兜底 15
        "lively_interval": _cfg_int_min(cfg.get("qq_lively_interval", 15), 15, 1),
        # 对话调节：单次回复字数上限（0=不限；非法值兜底 0）
        "max_reply_chars": _cfg_int_min(cfg.get("qq_max_reply_chars", 0), 0, 0),
        # 对话调节：每次对话最多回复次数（0=不限；10 分钟无回复自动重置）
        "max_replies_per_conversation": _cfg_int_min(cfg.get("qq_max_replies_per_conversation", 0), 0, 0),
        # 私信回复范围（设置→QQ；运行中改动即时生效）
        #   private_enable        总开关：false = 完全不回私信（含主人）
        #   private_master_only   true  = 只回主人私信（覆盖下面两项）
        #   private_reply_friend  是否回好友私信（sub_type=friend/group）
        #   private_reply_stranger 是否回陌生人私信（非好友/临时会话）
        "private_enable": str(cfg.get("qq_private_enable", "true")).lower() == "true",
        "private_master_only": str(cfg.get("qq_private_master_only", "false")).lower() == "true",
        "private_reply_friend": str(cfg.get("qq_private_reply_friend", "true")).lower() == "true",
        "private_reply_stranger": str(cfg.get("qq_private_reply_stranger", "true")).lower() == "true",
        # 点歌（官方插件「点歌」开关；默认开）
        "music_enabled": str(cfg.get("qq_music_enable", "true")).lower() == "true",
        # 自主学习（官方插件「自主学习」开关；默认开）
        "auto_learn_enable": str(cfg.get("qq_auto_learn_enable", "true")).lower() == "true",
        "auto_learn_search": str(cfg.get("qq_auto_learn_search", "true")).lower() == "true",
        "auto_learn_media": str(cfg.get("qq_auto_learn_media", "true")).lower() == "true",
        "auto_learn_links": str(cfg.get("qq_auto_learn_links", "true")).lower() == "true",
        "auto_learn_chats": str(cfg.get("qq_auto_learn_chats", "true")).lower() == "true",
        # 自主学习·表情收藏：把群里看到的动画表情自动存入自存表情池（供以后随机发送）
        "auto_learn_sticker_save": str(cfg.get("qq_auto_learn_sticker_save", "true")).lower() == "true",
        # 主人白名单（最多 5 个 QQ 号；第一位 = 主主人，负责共享记忆/离线补拉）
        "master_ids": _parse_master_ids(cfg),
        # 主主人（owner 兼容键，供离线补拉/共享记忆等"主号"逻辑使用）
        "owner_id": (_parse_master_ids(cfg) or [""])[0],
        # 插件全局总开关（启动器「插件」页管控；默认均启用）
        "adult_allowed": str(cfg.get("qq_adult_enable", "true")).lower() == "true",
        "galgame_allowed": str(cfg.get("qq_galgame_enable", "true")).lower() == "true",
        "slang_allowed": str(cfg.get("qq_slang_enable", "true")).lower() == "true",
        # F5-TTS 服务是否就绪（端口 9881）
        "f5tts_ready": f5tts_ready,
    }


def load_config():
    """兼容旧调用：返回完整 config dict"""
    return _load_config()