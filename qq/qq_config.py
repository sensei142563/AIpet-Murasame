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


def get_qq_config():
    """读取 QQ 相关配置（带默认值）"""
    cfg = _load_config()
    f5tts_ready = check_port_open(F5TTS_PORT)
    return {
        # NapCat WebSocket 地址（事件上报 + 调用 API 走同一连接）
        "ws_url": cfg.get("qq_napcat_ws", "ws://127.0.0.1:3001"),
        # NapCat WebUI (HTTP API，主要用于发送消息等)
        "http_url": cfg.get("qq_napcat_http", "http://127.0.0.1:6099"),
        # 是否在回复时携带表情包 gif
        "send_sticker": str(cfg.get("qq_send_sticker", "true")).lower() == "true",
        # 是否在回复时附带 F5-TTS 语音
        "send_voice": str(cfg.get("qq_send_voice", "false")).lower() == "true",
        # 是否启用图片识别（收到图片时用 qwen3-vl-plus 识别）
        "vision_enabled": str(cfg.get("qq_vision_enabled", "true")).lower() == "true",
        # 是否启用语音识别（收到语音消息时用 faster-whisper 转文字）
        "stt_enabled": str(cfg.get("qq_stt_enabled", "false")).lower() == "true",
        # 是否允许群聊（只 @ 时回复）
        "allow_groups": str(cfg.get("qq_allow_groups", "true")).lower() == "true",
        # F5-TTS 服务是否就绪（端口 9881）
        "f5tts_ready": f5tts_ready,
    }


def load_config():
    """兼容旧调用：返回完整 config dict"""
    return _load_config()