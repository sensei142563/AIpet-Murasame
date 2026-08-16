# -*- coding: utf-8 -*-
"""
长文本对话模型配置 — 统一管理模型 URL / Key / 模型名。

支持两种云端模型：
- qwen     → https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions  + qwen-plus
- deepseek → https://api.deepseek.com/chat/completions                            + deepseek-chat

由 config.json 的 "longtext_model" 字段控制（"qwen" / "deepseek"）。
视觉识别（屏幕/摄像头/QQ 图片）不受此影响，仍固定使用 qwen3-vl-plus。
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# 模型映射表
MODEL_MAP = {
    "qwen": {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen-plus",
        "key_field": "qwen",
    },
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "key_field": "deepseek",
    },
}


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_longtext_model_name():
    """读取 config.json 的 longtext_model 字段，返回 "qwen" / "deepseek"（默认 qwen）"""
    cfg = _load_config()
    val = str(cfg.get("longtext_model", "qwen")).strip().lower()
    if val not in MODEL_MAP:
        print(f"[ModelConfig] ⚠ 未知的 longtext_model: {val}，回退到 qwen")
        return "qwen"
    return val


def get_longtext_model_config():
    """
    返回长文本对话模型的完整配置：
        {
            "url":   API 请求地址,
            "model": 模型名 (qwen-plus / deepseek-chat),
            "api_key": 对应的 API Key,
            "name":   "qwen" / "deepseek"
        }
    若 API Key 缺失，返回 None（调用方应提示）。
    """
    name = get_longtext_model_name()
    info = MODEL_MAP[name]
    cfg = _load_config()

    api_key = (cfg.get("APIKEY") or {}).get(info["key_field"], "")
    if not api_key:
        print(f"[ModelConfig] ⚠ 未找到 {info['key_field']} API Key，请检查 config.json")
        return None

    return {
        "url": info["url"],
        "model": info["model"],
        "api_key": api_key,
        "name": name,
    }


def get_vision_model_config():
    """
    视觉识别模型配置（固定 qwen3-vl-plus，不受 longtext_model 影响）。
    返回 {"url": ..., "model": ..., "api_key": ...}，Key 缺失时返回 None。
    """
    cfg = _load_config()
    api_key = (cfg.get("APIKEY") or {}).get("qwen", "")
    if not api_key:
        print("[ModelConfig] ⚠ 未找到 qwen API Key，无法进行视觉识别")
        return None

    return {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen3-vl-plus",
        "api_key": api_key,
    }