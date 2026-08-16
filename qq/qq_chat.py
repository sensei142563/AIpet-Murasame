# -*- coding: utf-8 -*-
"""
QQ 对话封装 — 复用长文本记忆 + 丛雨人设 + 流式 AI。

与 longtext/longtext_manager.py 的区别：
- 不走 TTS 播放（QQ 端文字/图片/可选语音）
- 一次性收集完整回复（不用切句）
- 使用独立线程锁，避免与桌宠同时写记忆冲突

记忆分仓（V1.7）：
- 大号私聊 → long_history.json + 同步 history.json（与桌宠共享）
- 其他私聊 → data/qq_memory/<QQ号>.json（独立）
- 群聊     → data/qq_memory/group_<群号>.json（按群分仓）
"""

import os
import re
import time
import json
import threading

import requests

from longtext.longtext_history import load_long_history, save_long_history, sync_to_short_history
from pets.pet_registry import get_prompt_path, get_sticker_dir, get_pet_config


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 记忆线程锁：桌宠和 QQ 共用 long_history.json，必须互斥写
HISTORY_LOCK = threading.RLock()

# 可用表情包列表（文件名去扩展名）
STICKER_NAMES = []


def _load_sticker_names():
    """扫描当前角色表情包目录，返回表情包名列表"""
    global STICKER_NAMES
    sticker_dir = get_sticker_dir()
    if not sticker_dir:
        sticker_dir = os.path.join(BASE_DIR, "biaoqingbao")  # 兜底旧路径
    if os.path.isdir(sticker_dir):
        names = []
        for f in os.listdir(sticker_dir):
            if f.lower().endswith((".gif", ".png", ".jpg", ".jpeg")):
                names.append(os.path.splitext(f)[0])
        STICKER_NAMES = sorted(names)
    return STICKER_NAMES


def load_system_prompt():
    """读取当前角色长文本人设 prompt"""
    prompt_path = get_prompt_path("long")
    try:
        if prompt_path and os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
    except Exception as e:
        print(f"[QQChat] 读取 prompt 失败: {e}")
    pet_cfg = get_pet_config()
    pet_name = pet_cfg.get("display_name") or pet_cfg.get("name") or "桌宠"
    return (
        f"你是一个住在用户身边的人工智能桌宠角色——{pet_name}。"
        "请像真正的人类一样自然对话，不要机械重复设定词汇。"
        "直接说出你想说的话，不要有任何背景描写或动作描写。"
    )


def _build_messages(history):
    """
    构建消息列表（与 longtext_manager._chat_stream 同逻辑）：
    - priority=high → 提取为 system 级「最近的观察」
    - priority=low  → 完全过滤
    """
    messages = [{"role": "system", "content": load_system_prompt()}]

    high_observations = []
    for msg in (history or []):
        if not isinstance(msg, dict):
            messages.append(msg)
            continue
        pri = msg.get("priority")
        if pri == "high" and msg.get("content"):
            high_observations.append(msg.get("content", "").strip())
            continue
        if pri == "low":
            continue
        messages.append(msg)

    if high_observations:
        obs_text = "\n".join(f"- {obs}" for obs in high_observations[-5:])
        messages.append({
            "role": "system",
            "content": (
                "【最近的观察】你刚刚通过摄像头或屏幕看到了以下内容，"
                "这是你亲眼所见的事实，请自然地融入接下来的对话：\n"
                f"{obs_text}"
            ),
        })

    return messages


def _get_api_key():
    """读取 config 中的 qwen API Key"""
    import json as _json
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        return cfg.get("APIKEY", {}).get("qwen", "")
    except Exception:
        return ""


def _get_history_turns():
    """读取 config 的 longtext_max_history_turns（默认 20），统一桌宠与 QQ 记忆轮数"""
    import json as _json
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        val = int(cfg.get("longtext_max_history_turns", 20))
        return max(1, val)  # 至少 1 轮
    except Exception:
        return 20


def _load_session_history(session_key: str):
    """
    读取会话记忆：
    - session_key 为空 或 大号私聊 → long_history.json（共享）
    - 其他私聊/群聊 → 分仓记忆
    """
    turns = _get_history_turns()

    if not session_key:
        with HISTORY_LOCK:
            return load_long_history(max_turns=turns)

    try:
        from qq.qq_memory import resolve_memory_path
        path = resolve_memory_path(session_key)
        if path is None:
            # 大号 → 共享记忆
            with HISTORY_LOCK:
                return load_long_history(max_turns=turns)
        # 分仓
        from qq.qq_memory import load_memory
        return load_memory(session_key, max_turns=turns)
    except Exception as e:
        print(f"[QQChat] 读取分仓记忆失败: {e}")
        with HISTORY_LOCK:
            return load_long_history(max_turns=turns)


def _save_session_history(session_key: str, new_msgs: list):
    """
    保存会话记忆：
    - 大号私聊 → long_history.json + 同步 history.json
    - 其他 → 分仓文件（不写短文本）
    """
    turns = _get_history_turns()

    if not session_key:
        with HISTORY_LOCK:
            save_long_history(new_msgs, max_turns=turns)
            sync_to_short_history(new_msgs)
        return

    try:
        from qq.qq_memory import save_memory
        save_memory(session_key, new_msgs, max_turns=turns, sync_short=True)
    except Exception as e:
        print(f"[QQChat] 保存分仓记忆失败: {e}")


def chat_once(user_text: str, use_sticker: bool = True, vision_desc: str = None, session_key: str = None):
    """
    单轮对话（QQ 使用）：
    1. 读取会话记忆（最近 12 轮，大号共享 / 其他人分仓）
    2. 追加用户消息
    3. 调用长文本模型（qwen-plus / deepseek-chat，由 config 控制）生成完整回复
    4. 保存到对应记忆仓
    5. 返回 (回复文本, 表情包名 or None)

    表情包约定：AI 回复末尾若带 [表情:xxx]，解析为表情包选择并移除。

    session_key: "private_<QQ号>" 或 "group_<群号>"（None 表示默认共享记忆）
    """
    stickers = _load_sticker_names()

    # 1. 读取会话记忆
    history = _load_session_history(session_key)

    # 2. 组装请求（流式收集，降低首字延迟）
    messages = _build_messages(history)

    # 图片消息处理：text 为空但有 vision_desc → 用图片描述作为真实用户输入
    # （避免 [CQ:image...] 垃圾文本被当作对话内容，导致 AI 依赖历史记忆误判）
    if vision_desc:
        if user_text and user_text.strip():
            messages.append({
                "role": "user",
                "content": f"主人发来了一张图片，图片内容：{vision_desc}\n主人的话：{user_text}",
            })
        else:
            messages.append({
                "role": "user",
                "content": f"主人发来了一张图片，图片内容：{vision_desc}",
            })
    else:
        messages.append({"role": "user", "content": user_text})

    # 表情包指令（仅当启用且存在表情包时）
    # 允许 0~2 个：AI 根据语境自主决定发不发、发几张
    if use_sticker and stickers:
        sticker_hint = (
            "\n\n【表情包】回复的最后（换行后）可以根据语境附带 0~2 个表情包标记，"
            f"从以下列表中选择最贴合语境的一个或多个：{'、'.join(stickers)}。"
            '格式为 [表情:名称]，例如 [表情:撒娇] 或 [表情:思考][表情:肯定]。'
            '如果不需要表情包就不发，不要为了发而发。'
        )
        # 把表情包指令附加到最后一条 user 消息上
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += sticker_hint
        else:
            messages.append({"role": "user", "content": sticker_hint})

    # 3. 从 model_config 获取长文本模型（qwen / deepseek）
    from longtext.model_config import get_longtext_model_config
    mcfg = get_longtext_model_config()
    if not mcfg:
        return "（未配置对话模型 API Key）", None

    url = mcfg["url"]
    model_name = mcfg["model"]
    api_key = mcfg["api_key"]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": 512,  # QQ 场景短回复更自然
        "stream": True,
    }

    # 3. 流式收集完整回复
    full_reply = ""
    try:
        with requests.post(url, json=payload, headers=headers, stream=True, timeout=(15, 120)) as resp:
            if resp.status_code != 200:
                err_text = resp.text[:300]
                print(f"[QQChat] ⚠ API 错误 {resp.status_code}: {err_text}")
                return "（AI 暂时开小差了...）", None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if delta.get("reasoning_content"):
                        continue
                    content = delta.get("content")
                    if content:
                        full_reply += content
                except Exception:
                    continue
    except Exception as e:
        print(f"[QQChat] ⚠ 请求异常: {e}")
        return "（网络开小差了，等下再试试~）", None

    if not full_reply.strip():
        return "（什么都没说出来...）", None

    full_reply = full_reply.strip()

    # 4. 解析表情包标记（支持 0~2 个，去重）
    sticker_names = []
    if use_sticker and stickers:
        matches = re.findall(r"\[表情\s*[:：]\s*([^\]]+)\]", full_reply)
        for name in matches:
            name = name.strip()
            if name in stickers and name not in sticker_names:
                sticker_names.append(name)
        if matches:
            full_reply = re.sub(r"\[表情\s*[:：]\s*[^\]]+\]", "", full_reply).strip()

    # 5. 保存记忆（user + assistant 追加到对应会话仓）
    #    user 消息可读化：纯图片时用图片描述替代，避免记忆里存空白/垃圾文本
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    memory_user_text = user_text
    if vision_desc and (not user_text or not user_text.strip()):
        memory_user_text = f"[图片] {vision_desc}"
    elif vision_desc and user_text.strip():
        memory_user_text = f"{user_text}（附图：{vision_desc}）"
    new_msgs = [
        {"role": "user", "content": memory_user_text, "timestamp": timestamp},
        {"role": "assistant", "content": full_reply, "timestamp": timestamp},
    ]
    try:
        _save_session_history(session_key, new_msgs)
    except Exception as e:
        print(f"[QQChat] 保存记忆失败: {e}")

    return full_reply, sticker_names
