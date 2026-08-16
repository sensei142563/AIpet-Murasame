# -*- coding: utf-8 -*-
import base64
import os
from datetime import datetime

import requests

from tool.config import get_config
from tool.time_utils import build_time_context
from pets.pet_registry import get_prompt_path, get_short_emotion_dirs

url = get_config("./config.json")["local_api"]["cloud_api"]
model_type = get_config("./config.json")["model_type"]
if model_type != "local":
    API_key = get_config("./config.json")["APIKEY"][model_type]
if model_type == "deepseek":
    chat_model="deepseek-chat"
elif model_type == "qwen":
    chat_model="qwen-plus"

def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

def post(name: str, payload):
    payload_str = str(payload)
    if len(payload_str) > 200:
        payload_str = payload_str[:180] + "...(truncated)"
    print(f"[{now_time()}] [{name}] Prompt:{payload_str}")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + API_key
    }
    resp = requests.post(url, json={"payload": payload, "headers": headers})
    resp = resp.json()
    reply = ""
    if "choices" in resp:
        reply = resp['choices'][0]['message']['content']
    else:
        print(resp)
    print(f"[{now_time()}] [{name}] Reply:{reply}")
    return reply

def _prepare_priority_messages(history: list):
    """
    处理带 priority 字段的记忆：
    - priority=high: 提取为 system 级「最近的观察」强注入（高权重）
    - priority=low:  完全过滤（权重≈0，不再送入 API）
    - 其余: 正常对话消息
    返回 (过滤后的 history, 高权重观察列表)
    """
    identity = None
    filtered = []
    high_observations = []

    for msg in history:
        if not isinstance(msg, dict):
            filtered.append(msg)
            continue
        pri = msg.get("priority")
        if pri == "high" and msg.get("content"):
            high_observations.append(msg.get("content", "").strip())
            continue  # 高权重消息不放进正常序列（单独强注入）
        if pri == "low":
            continue  # 低权重消息完全过滤
        filtered.append(msg)

    # 分离出 system 身份（保持第一个 system prompt 不变）
    if filtered and filtered[0].get("role") == "system":
        identity = filtered[0]
        filtered = filtered[1:]

    return filtered, high_observations, identity


def cloud_talk(history: list, user_input: str, role: str):
    prompt_path = get_prompt_path("short")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            identity_default = f.read()
    except Exception:
        identity_default = "你是一个可爱的 AI 桌宠角色。"

    # 处理优先级记忆：过滤 low、提取 high
    filtered_history, high_observations, identity_msg = _prepare_priority_messages(history)

    messages = []
    # 1. system 身份（优先保留已有的 system，否则用默认身份）
    if identity_msg:
        messages.append(identity_msg)
    else:
        messages.append({"role": "system", "content": identity_default})

    # 2. 高权重「最近的观察」（识别触发的内容，仅本轮有高权重）
    if high_observations:
        obs_text = "\n".join(f"- {obs}" for obs in high_observations[-5:])  # 最多注入最近 5 条
        messages.append({
            "role": "system",
            "content": (
                "【最近的观察】你刚刚通过摄像头或屏幕看到了以下内容，"
                "这是你亲眼所见的事实，请自然地融入接下来的对话：\n"
                f"{obs_text}"
            ),
        })

    # 3. 正常对话历史
    messages.extend(filtered_history)

    time_ctx = build_time_context()
    if role != "system":
        user_input = f"[{time_ctx}]{user_input}"
        history.append({"role": role, "content": user_input})
        messages.append({"role": role, "content": user_input})
    else:
        # system 角色消息改为 user 角色发送，避免被 Qwen 忽略
        messages.append({"role": "user", "content": f"[{time_ctx}]\n{user_input}"})

    payload = {
        "messages": messages,
        "model": chat_model,
        "max_tokens": 4096,
        "stream": False,
    }
    reply = post(name=f"{model_type}-talk", payload=payload)
    history.append({"role": "assistant", "content": reply})  # 加入历史
    return reply, history

def cloud_portrait(sentence: str, history: list, type: str):
    # ===== 修复：杜绝「立绘历史污染」======================
    # 旧实现把完整 history（含历史返回的图层 ID）塞进 system，导致：
    #   某次 AI 偶发返回了另一套服装的 ID（如 A 模式出现 B 套 1475）→ 写入历史 →
    #   之后 AI 把历史当范例稳定复读 1475 → 僵脸/崩溃，滚雪球固化。
    # 现改为：只提炼「上次基础人物 ID」作衣服连贯参考，绝不把历史 ID 塞给 AI。
    # =====================================================
    import re as _re

    # ===== 从角色包读取立绘映射（无则回退默认提示）=====
    from pets.pet_registry import get_portrait_prompts
    portrait_cfg = get_portrait_prompts()
    set_cfg = portrait_cfg.get("sets", {}).get(type, {})
    if set_cfg:
        template = portrait_cfg.get("prompt_template", "")
        identity = template.replace("{layers_desc}", set_cfg.get("layers_desc", "")) \
                           .replace("{example}", set_cfg.get("example", ""))
    else:
        # 回退：角色无 portrait_prompts.json 时的最小提示
        identity = (
            f"你是一个立绘图层生成助手。用户会提供一个句子列表，"
            f"你需要根据每一个句子的情感来生成一张说话人的立绘所需的图层列表。"
            f"直接返回一个 JSON 列表，里面放上每个句子的图层ID。"
        )

    # ===== 只提炼「上次基础人物 ID」作衣服连贯参考（不把完整历史 ID 塞给 AI）=====
    outfit_id = None
    if history:
        for _sent, _rep in reversed(history):
            m = _re.search(r"\[\s*(\d+)", str(_rep))
            if m:
                outfit_id = m.group(1)  # reply 形如 [[基础人物, 表情, ...], ...]，首个数字即基础人物
                break
    outfit_hint = f"（保持衣服连贯：上次使用的基础人物 ID 为 {outfit_id}，本次请沿用同款衣服）" if outfit_id else "(本轮无历史，自由选衣服)"

    identity = f"{identity}\n{outfit_hint}"
    identity = f"{identity}\n{build_time_context()}"

    payload = {
        "messages": [{"role": "system", "content": identity},
                     {"role": "user", "content": sentence}],
        "model": chat_model,
        "max_tokens": 4096,
        "stream": False,
    }
    reply = post(name=f"{model_type}-portrait", payload=payload)
    history.append((sentence, reply))
    return reply, history

def cloud_translate(sentence: str):
    # 翻译规则按角色从 pet.json 的 translate_rules 读取（单一人设来源）；
    # 旧版硬编码保留为兜底（角色未配置时使用）。
    from pets.pet_registry import get_pet_config, get_active_pet_id
    identity = ""
    try:
        identity = ((get_pet_config() or {}).get("translate_rules") or "").strip()
    except Exception:
        identity = ""
    if not identity:
        if get_active_pet_id() == "murasame":
            identity = '你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：要将中文的“本座”翻译为“吾輩（わがはい）”；将“主人翻译为“ご主人（ごしゅじん）”；将“丛雨”翻译为“ムラサメ”；“小雨”则是丛雨的昵称，翻译为“ムラサメちゃん”。且日文要有强烈的古日语风格。你只需要返回翻译即可，不需要对其中的日文汉字进行注音。给你提供的格式是["句子1", "句子2", "句子3", .....]，必须严格按照原格式，输出一个json列表，逐句翻译。'
        else:
            identity = '你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：翻译自然、口语化、符合可爱少女说话习惯，不要古日语风格，不要添加任何说明，不需要注音。给你提供的格式是["句子1", "句子2", "句子3", .....]，必须严格按照原格式，输出一个json列表，逐句翻译，只输出纯JSON文本。'

    payload = {
            "messages": [{"role": "system", "content": identity},
                         {"role": "user", "content": sentence}],
            "model": chat_model,
            "max_tokens": 4096,
            "stream": False,
        }
    reply = post(name=f"{model_type}-translate", payload=payload)
    return reply

def cloud_emotion(history: list):
    # 只列出包含 asr.txt 的情感目录（过滤 long_chinese 等非情感参考）
    emotion_dirs = get_short_emotion_dirs()
    from pets.pet_registry import get_pet_config
    pet_cfg = get_pet_config()
    pet_name = pet_cfg.get("name", "丛雨")
    labels = '，'.join(emotion_dirs) if emotion_dirs else '平静'
    if emotion_dirs:
        example = f'如["{emotion_dirs[0]}", "{emotion_dirs[1] if len(emotion_dirs) > 1 else emotion_dirs[0]}"]'
    else:
        example = '如["平静", "平静"]'
    identity = f"你是一个情感分析助手，负责分析“{pet_name}”说的话的情感。你现在需要将用户输入的句子进行分析，综合用户的输入和{pet_name}的输出返回一个{pet_name}最新一句话每个分句情感的标签。你只可以选择的标签有{labels}。你需要直接返回一个情感列表，不需要其他任何内容。{example}"
    history_l = history[1:]
    payload = {
        "messages": [{"role": "system", "content": identity},
                     {"role": "user", "content": f"历史： {history_l}"}],
        "model": chat_model,
        "max_tokens": 4096,
        "stream": False,
    }
    reply = post(name=f"{model_type}-emotion", payload=payload)
    return reply
def cloud_vl(image_path: str):
    API_key = get_config("./config.json")["APIKEY"]["qwen"]
    identity = "你是一个AI桌宠的助手，你应该可以在屏幕上看到这个桌宠角色，是一个绿色头发的动漫人物。你需要简要描述用户正在做的事与使用的软件。我会将你的描述以system消息提供给另外一个处理语言的AI模型。只输出描述内容，且不要描述桌宠。"
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "messages": [{"role": "user", "content": [{"type": "image_url","image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                     {"type": "text", "text": identity}]}],
        "model": "qwen3-vl-plus",
        "max_tokens": 4096,
        "stream": False,
    }
    print(f"[{now_time()}] [qwen-vl] POST")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + API_key
    }
    resp = requests.post(url, json={"payload": payload, "headers": headers})
    resp = resp.json()
    reply = ""
    if "choices" in resp:
        reply = resp['choices'][0]['message']['content']
    else:
        print(resp)
    print(f"[{now_time()}] [qwen-vl] Reply:{reply}")
    return reply

