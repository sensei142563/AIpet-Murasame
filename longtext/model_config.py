# -*- coding: utf-8 -*-
"""
云端模型配置 — 统一管理各链路的模型 URL / Key / 模型名 / 推理等级。

支持两种云端模型族：
- qwen     → https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
- deepseek → https://api.deepseek.com/chat/completions

由 config.json 控制：
- "model_type"            短文本对话族（"local" / "deepseek" / "qwen"）
- "longtext_model"        长文本对话族（"qwen" / "deepseek"）
- "short_model_name"      短文本模型名（族默认：qwen-plus / deepseek-v4-flash）
- "longtext_model_name"   长文本模型名（族默认：deepseek-v4-flash / qwen-plus）
- "vision_model_name"     视觉模型名（默认 qwen3-vl-plus）
- "reasoning_level"       推理等级（off / low / high / max，默认 off）

注意：deepseek-chat / deepseek-reasoner 已于 2026-07-24 停用，
官方现只提供 deepseek-v4-flash / deepseek-v4-pro / deepseek-v4-flash-vision-exp。
URL 路由按模型名前缀决定（deepseek* → deepseek，其余 → dashscope），
不依赖族字段，避免"族选 qwen 但模型名填 deepseek-v4-flash"打到错误网关。
"""

import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

URL_QWEN = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
URL_DEEPSEEK = "https://api.deepseek.com/chat/completions"

# 模型族 → 默认模型名（deepseek 族已迁移到 V4 Flash）
FAMILY_DEFAULT_MODEL = {
    "deepseek": "deepseek-v4-flash",
    "qwen": "qwen-plus",
}

DEFAULT_VISION_MODEL = "qwen3-vl-plus"

# 推理等级白名单（DeepSeek: off/low/high/max；Qwen: off=关思考，任意开档=开思考）
REASONING_LEVELS = ("off", "low", "high", "max")


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _model_family(model_name: str) -> str:
    """按模型名前缀判断厂商（deepseek* → deepseek，其余 → qwen）"""
    name = str(model_name or "").strip().lower()
    return "deepseek" if name.startswith("deepseek") else "qwen"


def _resolve_url(model_name: str) -> str:
    return URL_DEEPSEEK if _model_family(model_name) == "deepseek" else URL_QWEN


def get_reasoning_level() -> str:
    """读取全局推理等级（off/low/high/max），非法值回退 off"""
    cfg = _load_config()
    val = str(cfg.get("reasoning_level", "off")).strip().lower()
    return val if val in REASONING_LEVELS else "off"


def supports_thinking(model_name: str) -> bool:
    """该模型名是否支持思考模式开关/强度控制"""
    name = str(model_name or "").strip().lower()
    return name.startswith("deepseek") or name.startswith("qwen3")


def build_reasoning_params(model_name: str, level: str = "off") -> dict:
    """
    按模型名 + 推理等级生成请求附加参数（不支持思考的模型返回空 dict）。

    - deepseek* : off → {"thinking": {"type": "disabled"}}
                  low/high/max → {"thinking": {"type": "enabled"}, "reasoning_effort": ...}
                  （DeepSeek 官方映射：low→low，medium/high→high，max→max）
    - qwen3*    : off → {"enable_thinking": false}，任意开档 → {"enable_thinking": true}
                  （Qwen 只有开关，没有强度档）
    - 其他模型  : 返回空 dict（qwen-plus / qwen-vl* 等不支持思考，不传参数避免 400）
    """
    level = str(level or "off").strip().lower()
    if level not in REASONING_LEVELS:
        level = "off"
    name = str(model_name or "").strip().lower()

    if name.startswith("deepseek"):
        if level == "off":
            return {"thinking": {"type": "disabled"}}
        effort = "low" if level == "low" else ("max" if level == "max" else "high")
        return {"thinking": {"type": "enabled"}, "reasoning_effort": effort}
    if name.startswith("qwen3"):
        return {"enable_thinking": level != "off"}
    return {}


# ==================== 长文本对话 ====================

def get_longtext_model_name():
    """读取 config.json 的 longtext_model 字段，返回 "qwen" / "deepseek"（默认 qwen）"""
    cfg = _load_config()
    val = str(cfg.get("longtext_model", "qwen")).strip().lower()
    if val not in FAMILY_DEFAULT_MODEL:
        print(f"[ModelConfig] ⚠ 未知的 longtext_model: {val}，回退到 qwen")
        return "qwen"
    return val


def get_longtext_model_config():
    """
    返回长文本对话模型的完整配置：
        {
            "url":   API 请求地址,
            "model": 模型名,
            "api_key": 对应的 API Key,
            "name":   "qwen" / "deepseek"（族）
            "reasoning": 推理等级附加参数（dict，可为空）
        }
    若 API Key 缺失，返回 None（调用方应提示）。
    """
    family = get_longtext_model_name()
    cfg = _load_config()
    model_name = str(cfg.get("longtext_model_name", "")).strip() or FAMILY_DEFAULT_MODEL[family]

    key_field = _model_family(model_name)  # key 跟随模型名实际厂商
    api_key = (cfg.get("APIKEY") or {}).get(key_field, "")
    if not api_key:
        print(f"[ModelConfig] ⚠ 未找到 {key_field} API Key，请检查 config.json")
        return None

    return {
        "url": _resolve_url(model_name),
        "model": model_name,
        "api_key": api_key,
        "name": family,
        "reasoning": build_reasoning_params(model_name, cfg.get("reasoning_level", "off")),
    }


# ==================== 短文本对话 ====================

def get_short_model_config():
    """
    返回短文本对话模型（cloud_API_chat 全链路）配置：
        {
            "url":   API 请求地址,
            "model": 模型名,
            "api_key": 对应的 API Key,
            "name":   "deepseek" / "qwen"（族）
            "reasoning": 推理等级附加参数（dict，可为空）
        }
    model_type == "local" 时返回 None（走本地 Ollama，不适用云端配置）。
    """
    cfg = _load_config()
    model_type = str(cfg.get("model_type", "qwen")).strip().lower()
    if model_type == "local":
        return None
    if model_type not in FAMILY_DEFAULT_MODEL:
        model_type = "qwen"

    model_name = str(cfg.get("short_model_name", "")).strip() or FAMILY_DEFAULT_MODEL[model_type]
    key_field = _model_family(model_name)
    api_key = (cfg.get("APIKEY") or {}).get(key_field, "")
    if not api_key:
        print(f"[ModelConfig] ⚠ 未找到 {key_field} API Key，请检查 config.json")
        return None

    return {
        "url": _resolve_url(model_name),
        "model": model_name,
        "api_key": api_key,
        "name": _model_family(model_name),
        "reasoning": build_reasoning_params(model_name, cfg.get("reasoning_level", "off")),
    }


# ==================== 视觉识别 ====================

def get_vision_model_config():
    """
    视觉识别模型配置（QQ 识图 / cloud_vl / 摄像头 / 常开摄像头 / 微信识图统一）。
    返回 {"url": ..., "model": ..., "api_key": ...}，Key 缺失时返回 None。
    """
    cfg = _load_config()
    model_name = str(cfg.get("vision_model_name", "")).strip() or DEFAULT_VISION_MODEL
    key_field = _model_family(model_name)
    api_key = (cfg.get("APIKEY") or {}).get(key_field, "")
    if not api_key:
        print(f"[ModelConfig] ⚠ 未找到 {key_field} API Key，无法进行视觉识别")
        return None

    return {
        "url": _resolve_url(model_name),
        "model": model_name,
        "api_key": api_key,
    }
