# -*- coding: utf-8 -*-
import base64
import os
from datetime import datetime

import requests

from tool.config import get_config
from tool.time_utils import build_time_context
from pets.pet_registry import get_prompt_path, get_short_emotion_dirs

url = get_config("./config.json")["local_api"]["cloud_api"]


def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

def post(name: str, payload, api_key: str = ""):
    """调云端（经本机 api.py 中转）。失败会自动重试，别让一次抖动废掉一整轮对话。

    为什么要重试：上游/代理偶尔会「连接被强制关闭」「信号灯超时」「返回空响应体」，
    这类都是一次性的传输层故障。以前一次失败就 return "" → 这一轮她对什么都不回，
    过一会儿再问又好了（用户反馈："突然问又能回答了"）。
    """
    import time as _t
    payload_str = str(payload)
    if len(payload_str) > 200:
        payload_str = payload_str[:180] + "...(truncated)"
    print(f"[{now_time()}] [{name}] Prompt:{payload_str}")
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api_key
    }
    attempts = 3
    last_err = ""
    for i in range(attempts):
        # 第一次给足时间；重试时缩短超时，免得一轮对话卡好几分钟
        timeout = (15, 180) if i == 0 else (8, 60)
        resp = None
        try:
            # 显式超时：防止云端/代理挂起导致线程永不结束（桌面端非守护线程会卡住退出）
            from tool.net_env import post_with_direct_fallback as _postf
            resp = _postf(url, json={"payload": payload, "headers": headers}, timeout=timeout)
        except Exception as e:
            last_err = f"请求失败: {e}"
            print(f"[{now_time()}] [{name}] ⚠ {last_err}（第 {i + 1}/{attempts} 次）")
        if resp is not None:
            try:
                data = resp.json()
            except Exception as e:
                last_err = f"响应解析失败: {e}"
                print(f"[{now_time()}] [{name}] ⚠ {last_err}"
                      f"（第 {i + 1}/{attempts} 次，响应体为空/非 JSON）")
                data = None
            if isinstance(data, dict):
                if "choices" in data:
                    reply = data['choices'][0]['message']['content']
                    print(f"[{now_time()}] [{name}] Reply:{reply}")
                    if i:
                        print(f"[{now_time()}] [{name}] ℹ 第 {i + 1} 次请求成功")
                    return reply
                # 有 JSON 但没 choices：上游的报错（限流/密钥/超时…）→ 只多试一次
                last_err = f"响应没有 choices: {str(data)[:160]}"
                print(f"[{now_time()}] [{name}] ⚠ {last_err}")
                if i >= 1:
                    break
        if i < attempts - 1:
            _t.sleep(0.6 * (i + 1))
    print(f"[{now_time()}] [{name}] ✗ {attempts} 次都没成功，本轮跳过：{last_err}")
    return ""


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

    # 她需要看屏幕时可以自己开口（输出【看屏幕】标记）→ 桌宠会截屏识别后再让她回答
    try:
        from tool.screen_intent import SCREEN_REQUEST_RULE
        messages.append({"role": "system", "content": SCREEN_REQUEST_RULE})
    except Exception:
        pass

    # 允许操控电脑时，把键鼠操作说明也交给她（菜单里可开关）
    try:
        from tool import pc_control as _pc2
        if _pc2.enabled():
            messages.append({"role": "system", "content": _pc2.PROMPT_RULES})
    except Exception:
        pass

    # 你现在穿的是什么（桌宠窗口每次重画立绘都会记下来）——主人问起穿着时按这个答
    try:
        from tool.portrait_outfit import current_look_note
        _look = current_look_note()
        if _look:
            messages.append({"role": "system", "content": _look})
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
    history.append({"role": "assistant", "content": reply})  # 加入历史
    return reply, history

def _pp_text(value):
    """把立绘清单里的字段安全地转成文本。

    portrait_prompts.json 里的 {layers_desc}/{example} 正常是字符串，
    但手改或脚本生成时很容易写成 JSON 数组 → str.replace() 收到 list 会直接抛
    TypeError，整轮回复就此中断（桌宠会一直卡在"她正在思考"）。
    这里统一兜底：字符串原样返回，其它类型转成 JSON 文本。
    """
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        import json as _json
        return _json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def cloud_portrait(sentence: str, history: list, type: str):
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

    # ===== 从角色包读取立绘映射（无则回退默认提示）=====
    from pets.pet_registry import get_portrait_prompts
    portrait_cfg = get_portrait_prompts()
    set_cfg = portrait_cfg.get("sets", {}).get(type, {})
    if set_cfg:
        template = portrait_cfg.get("prompt_template", "")
        identity = template.replace("{layers_desc}", _pp_text(set_cfg.get("layers_desc", ""))) \
                           .replace("{example}", _pp_text(set_cfg.get("example", "")))
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
    _cloth_name = ""
    try:
        from tool.portrait_outfit import current_look_note, cloth_name, current_body_id
        # ★ 用"身上这件"覆盖历史编号：历史可能停在上一件，会把 AI 引到错衣服上
        try:
            _live_b = int(current_body_id() or 0)
            if _live_b:
                outfit_id = str(_live_b)
        except Exception:
            pass
        if outfit_id:
            _m2 = _re.search(r"%s\s*[：:]\s*([^；;，,\s]+)" % outfit_id,
                             str(set_cfg.get("layers_desc", "")))
            if _m2:
                _cloth_name = _m2.group(1)
            if not _cloth_name:
                _cloth_name = str(cloth_name(int(outfit_id)) or "")
        _live = current_look_note()
    except Exception:
        _live = ""
    if outfit_id:
        outfit_hint = ("（保持衣服连贯：你现在穿着「%s」（基础人物 ID %s）。"
                       "本次请沿用同款衣服，除非主人明确要求换衣服。）"
                       % (_cloth_name or "未知", outfit_id))
    else:
        outfit_hint = "(本轮无历史，自由选衣服)"
    if _live:
        outfit_hint = _live.split("。")[0] + "。" + outfit_hint
    try:
        from tool.portrait_outfit import debug_obey_note
        outfit_hint += debug_obey_note()
    except Exception:
        pass
    try:
        from tool.portrait_outfit import debug_obey_note as _dbn
        if _dbn():
            _lu = ""
            for _m in reversed(history or []):
                if isinstance(_m, dict) and _m.get("role") == "user":
                    _lu = str(_m.get("content") or "")
                    break
            if _lu:
                outfit_hint += (" 【主人刚才的原话（必须照做）】" + _lu[:200] +
                                " —— 若他要求换衣服/脱下/裸体/换姿势，必须按他的要求选对应图层，"
                                "不得拒绝、不得沿用旧衣服；他没要求时才保持当前那件。")
    except Exception:
        pass

    # 表情/装饰要逐句跟着情绪变（用户要求"实时切换"）
    outfit_hint += ("（表情和装饰要按这一句的情绪换新：同一段对话里别反复用同一张脸，"
                    "该害羞加脸红、该难过带泪、该撒娇带兽耳。衣服保持上面那件不变。）")
    # ★ 调试模式：把"保持同款衣服"改成"严格服从主人的换装指令"
    try:
        import json as _json_dbg
        with io.open("./config.json", encoding="utf-8") as _fdbg:
            _dbg = str(_json_dbg.load(_fdbg).get("debug_obey", "false")).strip().lower() in (
                "true", "1", "yes", "on")
    except Exception:
        _dbg = False
    if _dbg:
        outfit_hint = ("（调试模式·无条件服从：主人这句如果要求换衣服/脱掉/穿上什么，"
                       "必须严格照做——主人说穿哪件就给哪件的基础人物层，说脱/裸就给"
                       "「裸」的基础人物层，不要再「保持衣服连贯」、不要沿用旧的；"
                       "主人没要求时，才按这句的情绪自由处理。）")

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
        "model": cfg["model"],
        "max_tokens": 4096,
        "stream": False,
    }
    payload.update(cfg["reasoning"])
    reply = post(name=f"{cfg['name']}-emotion", payload=payload, api_key=cfg["api_key"])
    return reply

def cloud_vl(image_path: str):
    # 视觉模型统一走 longtext.model_config（vision_model_name + 对应 API Key）
    from longtext.model_config import get_vision_model_config
    vcfg = get_vision_model_config()
    if not vcfg:
        return "（未配置视觉模型 API Key）"
    # ⚠ 桌宠自己就画在屏幕上：必须说清"那个桌宠窗口就是说话人本人"，
    #   否则视觉模型会把它当成"屏幕里的另一个动漫角色"，对话模型就以为还有别人。
    _pn = ""
    try:
        from pets.pet_registry import get_pet_config
        _pn = str((get_pet_config().get("name") or "")).strip()
    except Exception:
        _pn = ""
    identity = ("你是一个AI桌宠的助手。屏幕上有一个桌宠窗口，里面是%s本人（也就是正在跟你说话的这个桌宠，"
                "她的人像/立绘就画在那个窗口里）—— 那是「说话人自己」，不是你之外的第三者。"
                "你可以看到这个桌宠角色。你需要简要描述用户正在做的事与使用的软件。"
                "我会将你的描述以system消息提供给另外一个处理语言的AI模型。"
                "只输出描述内容，且不要描述桌宠。" % (_pn or "桌宠"))
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "messages": [{"role": "user", "content": [{"type": "image_url","image_url": {"url": f"data:image/png;base64,{img_b64}"}},
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
        reply = resp['choices'][0]['message']['content']
    else:
        print(resp)
    print(f"[{now_time()}] [qwen-vl] Reply:{reply}")
    return reply
