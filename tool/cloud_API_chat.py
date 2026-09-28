# -*- coding: utf-8 -*-
import base64
import os
from datetime import datetime

import requests

from tool.config import get_config
from tool.time_utils import build_time_context
from pets.pet_registry import get_chat_pet_id, get_prompt_path, get_short_emotion_dirs

url = get_config("./config.json")["local_api"]["cloud_api"]


def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

def post(name: str, payload, api_key: str = ""):
    payload_str = str(payload)
    if len(payload_str) > 200:
        payload_str = payload_str[:180] + "...(truncated)"
    print(f"[{now_time()}] [{name}] Prompt:{payload_str}")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api_key
    }
    try:
        # 显式超时：防止云端/代理挂起导致线程永不结束（桌面端非守护线程会卡住退出）
        # 走系统代理失败时自动改「直连」重试一次（代理端口没开时桌宠不再哑掉）
        from tool.net_env import post_with_direct_fallback as _postf
        resp = _postf(url, json={"payload": payload, "headers": headers},
                      timeout=(15, 180))
    except Exception as e:
        print(f"[{now_time()}] [{name}] ⚠ 请求失败: {e}")
        return ""
    try:
        resp = resp.json()
    except Exception as e:
        print(f"[{now_time()}] [{name}] ⚠ 响应解析失败: {e}")
        return ""
    reply = ""
    if "choices" in resp:
        reply = resp['choices'][0]['message']['content']
    else:
        print(resp)
    print(f"[{now_time()}] [{name}] Reply:{reply}")
    return reply

def _short_model_cfg():
    """短文本链路模型配置（model_type=local 时返回 None）"""
    from longtext.model_config import get_short_model_config
    return get_short_model_config()

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
    cfg = _short_model_cfg()
    if not cfg:
        return "（未配置对话模型 API Key）", history

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

    # 1.65 他在问我屏幕上的事？→ 当场抓屏看一眼，再连着描述一起回答（见 tool/screen_intent）
    try:
        from tool import screen_intent as _si
        if _si.needs_screen_look(user_input or ""):
            _desc, _shot = _si.look_now()
            if _desc:
                messages.append({"role": "system",
                                 "content": _si.build_screen_prompt(_desc, user_input)})
                print("[看屏幕] 已当场抓屏识别（%d 字）" % len(_desc))
            else:
                print("[看屏幕] 他想让我看屏幕，但抓屏/识别没成功（%s）" % (_shot or "抓屏失败"))
    except Exception as _e:
        print("[看屏幕] ⚠ 失败: %s" % _e)

    # 1.7 她自己的长期记忆（自主学习攒的：关于主人的事、情节、刚才在忙什么、日记）
    try:
        from tool import self_learn as _sl_note
        _memo = _sl_note.memory_note(user_input or "")
        if _memo:
            messages.append({"role": "system", "content": _memo})
    except Exception:
        pass

    # 1.8 提醒/待办语法（她能帮主人记事，见 tool/reminder 的 prompt_rules）
    try:
        from tool import reminder as _rm_rules
        if _rm_rules.enabled():
            messages.append({"role": "system", "content": _rm_rules.prompt_rules()})
    except Exception:
        pass

    # 1.9 她的行动边界（哪些能自己做、哪些要主人开口、哪些永远不做）
    try:
        from tool import autonomy as _au_note
        messages.append({"role": "system", "content": _au_note.note()})
    except Exception:
        pass

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

    # 当前时间（精确到分钟）+ 命中天气提问时注入实时天气：
    # 模型据此如实回答"现在几点/今天天气"，不再靠猜或含糊其辞
    time_ctx = build_time_context()
    wx_note = ""
    try:
        from tool.weather_utils import weather_note_if_asked
        wx_note = weather_note_if_asked(user_input) or ""
    except Exception:
        pass
    if role != "system":
        if wx_note:
            user_input = f"[{time_ctx}]\n{wx_note}\n{user_input}"
        else:
            user_input = f"[{time_ctx}]{user_input}"
        history.append({"role": role, "content": user_input})
        messages.append({"role": role, "content": user_input})
    else:
        # system 角色消息改为 user 角色发送，避免被 Qwen 忽略
        if wx_note:
            messages.append({"role": "user", "content": f"[{time_ctx}]\n{wx_note}\n{user_input}"})
        else:
            messages.append({"role": "user", "content": f"[{time_ctx}]\n{user_input}"})

    payload = {
        "messages": messages,
        "model": cfg["model"],
        "max_tokens": 4096,
        "stream": False,
    }
    payload.update(cfg["reasoning"])  # 推理等级附加参数（off 时可能为空 dict）
    reply = post(name=f"{cfg['name']}-talk", payload=payload, api_key=cfg["api_key"])
    # 提醒：模型写了【提醒】标记 → 在这里记下/取消/列出来，并把标记从要说出口的话里去掉
    try:
        from tool import reminder as _rm_reply
        reply = _rm_reply.handle_reply(reply)
    except Exception as _e:
        print(f"[云端] [提醒] ⚠ 处理失败: {_e}")
    history.append({"role": "assistant", "content": reply})  # 加入历史
    return reply, history

def cloud_portrait(sentence: str, history: list, type: str, live2d: bool = False):
    # ===== 修复：杜绝「立绘历史污染」======================
    # 旧实现把完整 history（含历史返回的图层 ID）塞进 system，导致：
    #   某次 AI 偶发返回了另一套服装的 ID（如 A 模式出现 B 套 1475）→ 写入历史 →
    #   之后 AI 把历史当范例稳定复读 1475 → 僵脸/崩溃，滚雪球固化。
    # 现改为：只提炼「上次基础人物 ID」作衣服连贯参考，绝不把历史 ID 塞给 AI。
    # =====================================================
    import re as _re

    cfg = _short_model_cfg()
    if not cfg:
        return "（未配置对话模型 API Key）", history

    # ===== Live2D 模式：把可选表情/动作列表交给 AI 自己选（用户 2026-09-24 拍板）=====
    if live2d:
        from tool.chat import build_live2d_prompt
        l2d_prompt = build_live2d_prompt()
        if l2d_prompt:
            payload = {
                "messages": [{"role": "system",
                              "content": f"{l2d_prompt}\n{build_time_context()}"},
                             {"role": "user", "content": sentence}],
                "model": cfg["model"],
                "max_tokens": 4096,
                "stream": False,
            }
            payload.update(cfg["reasoning"])
            reply = post(name=f"{cfg['name']}-live2d", payload=payload,
                         api_key=cfg["api_key"])
            history.append((sentence, reply))
            return reply, history

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
        "model": cfg["model"],
        "max_tokens": 4096,
        "stream": False,
    }
    payload.update(cfg["reasoning"])
    reply = post(name=f"{cfg['name']}-portrait", payload=payload, api_key=cfg["api_key"])
    history.append((sentence, reply))
    return reply, history

def cloud_translate(sentence: str):
    # 翻译规则按角色从 pet.json 的 translate_rules 读取（单一人设来源）；
    # 旧版硬编码保留为兜底（角色未配置时使用）。
    cfg = _short_model_cfg()
    if not cfg:
        return "（未配置对话模型 API Key）"

    from pets.pet_registry import get_pet_config, get_active_pet_id
    identity = ""
    try:
        identity = ((get_pet_config(get_chat_pet_id()) or {}).get("translate_rules") or "").strip()
    except Exception:
        identity = ""
    if not identity:
        if get_chat_pet_id() == "murasame":
            identity = '你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：要将中文的“本座”翻译为“吾輩（わがはい）”；将“主人翻译为“ご主人（ごしゅじん）”；将“丛雨”翻译为“ムラサメ”；“小雨”则是丛雨的昵称，翻译为“ムラサメちゃん”。且日文要有强烈的古日语风格。你只需要返回翻译即可，不需要对其中的日文汉字进行注音。给你提供的格式是["句子1", "句子2", "句子3", .....]，必须严格按照原格式，输出一个json列表，逐句翻译。'
        else:
            identity = '你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：翻译自然、口语化、符合可爱少女说话习惯，不要古日语风格，不要添加任何说明，不需要注音。给你提供的格式是["句子1", "句子2", "句子3", .....]，必须严格按照原格式，输出一个json列表，逐句翻译，只输出纯JSON文本。'

    payload = {
            "messages": [{"role": "system", "content": identity},
                         {"role": "user", "content": sentence}],
            "model": cfg["model"],
            "max_tokens": 4096,
            "stream": False,
        }
    payload.update(cfg["reasoning"])
    reply = post(name=f"{cfg['name']}-translate", payload=payload, api_key=cfg["api_key"])
    return reply

def cloud_emotion(history: list):
    # 只列出包含 asr.txt 的情感目录（过滤 long_chinese 等非情感参考）
    cfg = _short_model_cfg()
    if not cfg:
        return "（未配置对话模型 API Key）"

    emotion_dirs = get_short_emotion_dirs()
    from pets.pet_registry import get_pet_config
    pet_cfg = get_pet_config(get_chat_pet_id())
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
        "model": cfg["model"],
        "max_tokens": 4096,
        "stream": False,
    }
    payload.update(cfg["reasoning"])
    reply = post(name=f"{cfg['name']}-emotion", payload=payload, api_key=cfg["api_key"])
    return reply

def cloud_vl(image_path: str):
    """云端识图：把图片交给 vision_model_name 配置的模型，返回描述文字。

    ⚠ 拿不到描述时**一律返回空串**（原因只打印在控制台）：调用方会把返回值当成
      "我亲眼看到的屏幕内容"直接塞进提示词（见 classes/murasame_class.py 的截图段与
      main.py 的 _screenshot_task）。早先这里返回的是一句人话提示，于是她会一本正经地
      评论那句提示（踩过）—— 所以本函数**任何**失败分支都只能返回空串。
    """
    # 视觉模型统一走 longtext.model_config（vision_model_name + 对应 API Key）
    from longtext.model_config import get_vision_model_config
    vcfg = get_vision_model_config()
    if not vcfg:
        print(f"[{now_time()}] [qwen-vl] ⚠ 没配视觉模型（config.json 的 vision_model_name "
              f"与对应 APIKEY）→ 本次不识别")
        return ""
    # 不再写死"绿色头发"：本仓库有 3 个角色（murasame/noir/natsume），
    # 说错外貌会让视觉模型顺着提示编一个不存在的人。
    identity = ("你是一个AI桌宠的助手。屏幕上会有一个桌宠角色，请忽略它。"
                "你需要简要描述用户正在做的事与使用的软件。"
                "我会将你的描述以system消息提供给另外一个处理语言的AI模型。"
                "只输出描述内容，且不要描述桌宠。")
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        print(f"[{now_time()}] [qwen-vl] ⚠ 读图失败: {e}")
        return ""
    # 按扩展名给对 MIME：屏幕截图是 png，但别处存过来的可能是 jpg
    _ext = os.path.splitext(str(image_path))[1].lower().lstrip(".")
    _mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp",
             "bmp": "bmp", "gif": "gif"}.get(_ext, "png")

    payload = {
        "messages": [{"role": "user", "content": [{"type": "image_url","image_url": {"url": f"data:image/{_mime};base64,{img_b64}"}},
                     {"type": "text", "text": identity}]}],
        "model": vcfg["model"],
        "max_tokens": 4096,
        "stream": False,
    }
    print(f"[{now_time()}] [qwen-vl] POST")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + vcfg["api_key"]
    }
    try:
        # 走系统代理失败时自动改「直连」重试一次（代理端口没开时桌宠不再哑掉）
        from tool.net_env import post_with_direct_fallback as _postf
        resp = _postf(url, json={"payload": payload, "headers": headers},
                      timeout=(15, 180))
    except Exception as e:
        print(f"[{now_time()}] [qwen-vl] ⚠ 请求失败: {e}")
        return ""
    try:
        resp = resp.json()
    except Exception as e:
        print(f"[{now_time()}] [qwen-vl] ⚠ 响应解析失败: {e}")
        return ""
    reply = ""
    if "choices" in resp:
        try:
            reply = resp['choices'][0]['message']['content'] or ""
        except Exception as e:
            print(f"[{now_time()}] [qwen-vl] ⚠ 响应结构不认识: {e}")
            reply = ""
    else:
        print(f"[{now_time()}] [qwen-vl] ⚠ 云端没给 choices: {str(resp)[:200]}")
    print(f"[{now_time()}] [qwen-vl] Reply:{reply}")
    return reply
