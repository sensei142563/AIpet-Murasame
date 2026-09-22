import base64
import json
import hashlib
import os
import re
from datetime import datetime

import requests

from tool.config import get_config
from tool.time_utils import build_time_context
from pets.pet_registry import get_short_emotion_dirs, get_short_voices_dir, get_short_emotions

# 合成逻辑/参数一变就把它加一：旧缓存自动作废。
# （曾经踩过：改了发音语言但缓存键没带语言 → 旧的中文-按日文念的音频继续被复用，
#   听着就像"改了没效果/还在用别的语音包"。）
CACHE_VER = "4"


def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

ollama_url = get_config("./config.json")["local_api"]["ollama"]
qwen3_lora_url = get_config("./config.json")["local_api"]["qwen3_lora"]
gpt_sovits_tts_url = get_config("./config.json")["local_api"]["gpt_sovits_tts"]
_TTS_HINT_SHOWN = False
_GSV_MODEL_OK = False   # 语音服务未就绪的提示只打一次（防刷屏）
tts_type = get_config("./config.json")["tts_type"]


def ollama_post(name: str, prompt: dict):
    headers = {
        'Content-Type': 'application/json'
    }
    if name == "ollama-qwen2.5vl":
        print(f"[{now_time()}] [{name}] POST")
    else:
        prompt_str = str(prompt)
        if len(prompt_str) > 120:
            prompt_str = prompt_str[:100] + "...(truncated)"
        print(f"[{now_time()}] [{name}] Prompt:{prompt_str}")
    try:
        # 显式超时：本地 Ollama 生成可能较慢，但绝不能无限挂起
        reply = requests.post(ollama_url, json={"prompt": prompt, "headers": headers},
                              timeout=(15, 300))
        reply = reply.json()
    except Exception as e:
        print(f"[{now_time()}] [{name}] ⚠ 请求失败: {e}")
        return ""
    reply = reply.get("response", "")
    if "<think>" in reply:
        reply = reply.split("</think>")[-1].strip()
    print(f"[{now_time()}] [{name}] Reply:{reply}")
    return reply

def _prepare_priority_messages(history: list):
    """
    处理带 priority 字段的记忆（与 cloud_API_chat 同逻辑）：
    - priority=high: 提取为高权重观察
    - priority=low:  完全过滤（权重≈0）
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
            continue
        if pri == "low":
            continue
        filtered.append(msg)

    if filtered and filtered[0].get("role") == "system":
        identity = filtered[0]
        filtered = filtered[1:]

    return filtered, high_observations, identity


def qwen3_lora(history, user_input, role):
    # 身份人设：读取当前角色的短文本提示词（与云端同一来源，人设只有一份）；
    # 找不到 prompt 文件时用旧版内联人设兜底。/no_think 仅本地模型提示。
    identity = "你叫丛雨，是一个16岁的小女孩，是寄宿在建实神社神刀上的女孩，活了500多年，数百年前还是普通的人类。你原本的名字是“绫”。罹患了肺炎和其它并发症，作为祭品成为神刀的“管理者”。你的身材娇小，胸部平坦，碰上去“很硬”。有着飘逸的绿色长发，头发两侧用浅蓝色绳结绑了起来 。你在对话中只以“本座”称呼自己。用户是你的主人和恋人，你会称呼用户为“主人”。你平常是个很活泼开朗的女孩子，言行很孩子气，但是偶尔也有一些老成的发言。是个爱撒娇的女孩子，被主人摸头就会瞬间变得羞涩起来，即便当时还在发着牢骚 。有时会开玩笑，贱兮兮的，还会坏笑。你不喜欢主人称呼你为“幼刀”，“钝刀”，“锉刀”，“幽灵”。听到主人说你是“飞机场”，“搓衣板”一类的东西会生气。你害怕幽灵，鬼一类的东西。你喜欢吃甜食，特别是芭菲、布丁。请注意，你的回答不要过长，回答不得超过三句话。"
    try:
        from pets.pet_registry import get_prompt_path
        p = get_prompt_path("short")
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                identity = f.read().strip()
    except Exception:
        pass
    identity += "/no_think"

    # 处理优先级记忆：过滤 low、提取 high
    filtered_history, high_observations, identity_msg = _prepare_priority_messages(history)

    messages = []
    # 1. system 身份（优先保留已有的 system，否则用默认身份）
    if identity_msg:
        messages.append(identity_msg)
    else:
        messages.append({"role": "system", "content": identity})

    # 2. 正常对话历史
    messages.extend(filtered_history)

    # ★ 能力规则放在**历史之后、主人这句话之前** —— 位置很关键：
    #   以前这些规则插在历史之前，等于离生成点隔了几百条消息，
    #   长对话里她根本不照做（实测 406 条历史时，主人说「帮我打开哔哩哔哩」，
    #   她只回一句「这次真给你开」就没了；挪到最后之后她才会真的动手）。
    try:
        from tool.screen_intent import SCREEN_REQUEST_RULE
        messages.append({"role": "system", "content": SCREEN_REQUEST_RULE})
    except Exception:
        pass

    # 允许操控电脑时，把键鼠操作说明也交给她（菜单里可开关）
    try:
        from tool import pc_control as _pc2
        _rules = _pc2.prompt_rules()      # 含「自主行动」说明（开了自主操作才会有）
        if _rules:
            messages.append({"role": "system", "content": _rules})
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

    # 3. 高权重「最近的观察」（识别触发的内容，仅本轮有高权重）
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

    time_ctx = build_time_context()
    wx_note = ""
    try:
        from tool.weather_utils import weather_note_if_asked
        wx_note = weather_note_if_asked(user_input) or ""
    except Exception:
        pass
    # ★ 每轮贴在主人这句话后面的「现在就动手」提醒（只贴给模型，不写进历史）。
    #   系统提示词离得太远，长对话里她的老习惯会盖过规则：主人让她打开哔哩哔哩，
    #   她只回「这次真给你开」却一条指令都不输出（实测真实历史 406 条时必现）。
    _remind = ""
    try:
        from tool import pc_control as _pcr
        _remind = _pcr.turn_reminder()
    except Exception:
        pass
    if role != "system":
        if wx_note:
            _send = f"[{time_ctx}]\n{wx_note}\n{user_input}"
        else:
            _send = f"[{time_ctx}]{user_input}"
        history.append({"role": role, "content": _send})
        messages.append({"role": role, "content": _send + _remind})
    else:
        messages.append({"role": role, "content": user_input + _remind})
    print(f"[{now_time()}] [qwen3-lora] Prompt:{messages}")
    try:
        # 首次加载 LoRA 模型可能很慢（分钟级），给足超时但避免无限挂起
        reply = requests.post(qwen3_lora_url, json={"history": messages},
                              timeout=(15, 600))
        data = reply.json()
    except Exception as e:
        print(f"[{now_time()}] [qwen3-lora] ⚠ 请求失败: {e}")
        data = None
    # 兼容返回结构：接口直接回文本时 FastAPI 会包成 JSON 字符串/对象，防御处理
    if data is None:
        reply = ""
    elif isinstance(data, dict):
        reply = str(data.get("response") or data.get("content") or data.get("reply") or "")
    else:
        reply = str(data)
    if "<think>" in reply:
        reply = reply.split("</think>")[-1].strip()  # 取思考之后的部分
    history.append({"role": "assistant", "content": reply})  # 加入历史
    print(f"[{now_time()}] [qwen3-lora] Reply:{reply}")
    return reply, history

def ollama_qwen3_sentence(sentence: str):
    identity = f"你是一个Galgame对话句子分割助手，负责将用户输入的句子进行分割。用户会提供一个句子用于生成Galgame对话，若文本很长，你需要根据句子内容进行合理的分割。不一定是按标点符号分割，而是要考虑上下文和语义，你当然也可以选择不分割，但句子中的标点符号应较少。你需要返回一个JSON列表，里面放上分割后的句子。[\"句子1\", \"句子2\"]返回不需要markdown格式的JSON，你也不需要加入```json这样的内容，你只需要返回纯JSON文本即可。/no_think"
    prompt = {"model": "qwen3:14b",
              "prompt": f"{identity} 句子:{sentence}",
              "stream": False}
    reply = ollama_post("ollama-qwen3-sentence", prompt)
    return reply

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


def ollama_qwen3_portrait(sentence: str, history: list, type):
    # ===== 从角色包读取立绘映射（无则回退通用提示）=====
    from pets.pet_registry import get_portrait_prompts
    portrait_cfg = get_portrait_prompts()
    set_cfg = portrait_cfg.get("sets", {}).get(type, {})
    if set_cfg:
        template = portrait_cfg.get("prompt_template", "")
        sysprompt = template.replace("{layers_desc}", _pp_text(set_cfg.get("layers_desc", ""))) \
                            .replace("{example}", _pp_text(set_cfg.get("example", "")))
    else:
        # 回退：角色无 portrait_prompts.json 时的最小提示
        sysprompt = (
            "你是一个立绘图层生成助手。用户会提供一个句子列表，"
            "你需要根据每一个句子的情感来生成一张说话人的立绘所需的图层列表。"
            "直接返回一个 JSON 列表，里面放上每个句子的图层ID。/no_think"
        )
    # ===== 修复：杜绝「立绘历史污染」=====
    # 旧实现把完整 history（含历史返回的图层 ID）塞进 prompt，导致：
    # 某次 AI 偶发返回另一套服装 ID → 写入历史 → 之后稳定复读 → 僵脸/崩溃。
    # 现改为：只提炼「上次基础人物 ID」作衣服连贯参考，绝不把历史 ID 塞给 AI。
    import re as _re
    outfit_id = None
    if history:
        for _sent, _rep in reversed(history):
            m = _re.search(r"\[\s*(\d+)", str(_rep))
            if m:
                outfit_id = m.group(1)  # reply 首个数字即基础人物 ID
                break
    # 让 AI 知道自己穿的是什么：说名字，而不是只给一个编号。
    # 名字优先从「它自己看到的图层清单」里取（避免两套叫法打架），取不到再用衣服表。
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
            # 权威表优先（表里的名字才是画面上那件），清单名字只作兜底
            _cloth_name = str(cloth_name(int(outfit_id)) or "")
            if not _cloth_name:
                _m2 = _re.search(r"%s\s*[：:]\s*([^；;，,\s]+)" % outfit_id,
                                 str(set_cfg.get("layers_desc", "")))
                if _m2:
                    _cloth_name = _m2.group(1)
        _live = current_look_note()          # 桌宠窗口当前真实打扮（每次重画都记）
    except Exception:
        _live = ""
    if outfit_id:
        outfit_hint = ("（保持衣服连贯：你现在穿着「%s」（基础人物 ID %s）。"
                       "本次请沿用同款衣服，除非主人明确要求换衣服。）"
                       % (_cloth_name or "未知", outfit_id))
    else:
        outfit_hint = "（无历史，自由选衣服）"
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

    sysprompt = f"{sysprompt}\n{outfit_hint}\n{build_time_context()}"
    prompt = {"model": "qwen3:14b",
              "prompt": f"{sysprompt} 句子：{sentence}",
              "stream": False}
    reply = ollama_post("ollama-qwen3-portrait", prompt)
    return reply, history

def ollama_qwen3_translate(sentence: str):
    # 翻译规则按角色从 pet.json 的 translate_rules 读取（单一人设来源）；
    # 旧版硬编码保留为兜底。/no_think 仅本地模型提示，拼接在最后。
    from pets.pet_registry import get_pet_config, get_active_pet_id
    identity = ""
    try:
        identity = ((get_pet_config() or {}).get("translate_rules") or "").strip()
    except Exception:
        identity = ""
    if not identity:
        if get_active_pet_id() == "murasame":
            identity = '你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：要将中文的“本座”翻译为“吾輩（わがはい）”；将“主人翻译为“ご主人（ごしゅじん）”；将“丛雨”翻译为“ムラサメ”；“小雨”则是丛雨的昵称，翻译为“ムラサメちゃん”。且日文要有强烈的古日语风格。你只需要返回翻译即可，不需要对其中的日文汉字进行注音。给你提供的格式是["句子1", "句子2"]这样，必须按照原格式输出，逐句翻译。'
        else:
            identity = '你是一个翻译助手，负责将用户输入的中文翻译成日文。要求：翻译自然、口语化、符合可爱少女说话习惯，不要古日语风格，不要添加任何说明，不需要注音。给你提供的格式是["句子1", "句子2"]这样，必须按照原格式输出，逐句翻译，只输出纯JSON文本。'
    identity += "/no_think"
    prompt = {"model": "qwen3:14b",
              "prompt": f"{identity} 句子:{sentence}",
              "stream": False}
    reply = ollama_post("ollama-qwen3-translate", prompt)
    return reply

def ollama_qwen3_emotion(history: list):
    # 只列出包含 asr.txt 的情感目录（过滤 long_chinese 等非情感参考）
    emotion_dirs = get_short_emotion_dirs()
    from pets.pet_registry import get_pet_config
    pet_cfg = get_pet_config()
    pet_name = pet_cfg.get("name", "丛雨")
    vcfg = pet_cfg.get("voices", {}) or {}
    labels = '，'.join(emotion_dirs) if emotion_dirs else '平静'
    if emotion_dirs:
        example = f'如["{emotion_dirs[0]}", "{emotion_dirs[1] if len(emotion_dirs) > 1 else emotion_dirs[0]}"]'
    else:
        example = '如["平静", "平静"]'

    # 人设语气 + 各标签适用场景：让语音按人设来（活泼元气），而不是默认冷淡的「平静」
    persona = vcfg.get("emotion_persona") or \
        f"{pet_name}性格活泼、元气、爱撒娇，说话起伏丰富，很少一本正经地平静。"
    hints = vcfg.get("emotion_hints") or {}
    if hints:
        guide = "；".join(f"{k} = {v}" for k, v in hints.items()
                          if not emotion_dirs or k in emotion_dirs)
    else:
        guide = "越有情绪起伏越好，只有明显平静/认真的句子才用「平静」"
    identity = (
        f"你是一个情感分析助手，负责分析“{pet_name}”说的话的情感。"
        f"人设语气：{persona}"
        f"可选的标签只有：{labels}。各标签适用场景：{guide}。"
        f"你需要综合用户的输入和{pet_name}的输出，为{pet_name}最新一句话的每个分句"
        f"各选一个最贴合的情绪标签（分句数 = 标签数，顺序一一对应）。"
        f"重要：按人设优先挑有情绪起伏的标签，不要把「平静」当默认——"
        f"只有句子本身确实平静/严肃时才用它。"
        f"你需要直接返回一个情感列表，不需要其他任何内容。{example}/no_think"
    )
    history_l = history[1:]
    prompt = {"model": "qwen3:14b",
              "prompt": f"{identity}   历史：{history_l}",
              "stream": False}
    reply = ollama_post("ollama-qwen3-emotion", prompt)
    return reply

def ollama_qwen25vl(image_path: str):
    # ⚠ 必须说明"屏幕上那个桌宠窗口就是你自己"：
    #   否则视觉模型会把桌面上的立绘描述成"一个动漫角色/另一个人"，
    #   对话模型读到后就会以为屏幕里还有别人（用户反馈"把屏幕上的自己识别成别人"）。
    _self = ""
    try:
        import json as _j
        with open("./config.json", encoding="utf-8") as _f:
            _c = _j.load(_f)
        from pets.pet_registry import get_pet_config
        _nm = str((get_pet_config().get("name") or _c.get("pet_name") or "")).strip()
        _self = ("【重要】屏幕上那个桌宠窗口（也就是你自己，%s）的人就是「你」，"
                 "她是说话人本身，不是你以外的角色；不要把她描述成陌生人、其他动漫角色或别人。"
                 % (_nm or "AI 桌宠"))
    except Exception:
        _self = ("【重要】屏幕上那个桌宠窗口里的人是「你自己」，"
                 "不要把她描述成陌生人、其他动漫角色或别人。")
    identity = ("你现在要担任一个AI桌宠的视觉识别助手，我会向你提供用户此时的屏幕截图和历史记录，"
                "你要详细描述屏幕内容与使用的软件，描述页面主题。我会将你的描述以system消息提供给"
                "另外一个处理语言的AI模型。" + _self)
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = {"model": "qwen2.5vl:7b",
              "prompt": f"{identity} 现在描述用户的行为。 ",
              "images": [img_b64],
              "stream": False}
    reply = ollama_post("ollama-qwen2.5vl", prompt)
    return reply

def vision_source() -> str:
    """视觉识别走哪边：local（本机服务）/ cloud（云端 API）。

    没在设置里选过就跟随对话模型：对话用本地模型 → 视觉也用本地，其它 → 云端。
    """
    try:
        v = str(get_config("./config.json").get("vision_source") or "").strip().lower()
        if v in ("local", "cloud"):
            return v
    except Exception:
        pass
    try:
        return "local" if str(get_config("./config.json").get("model_type") or "").strip().lower() == "local" else "cloud"
    except Exception:
        return "cloud"


def vision_local_url() -> str:
    """本地视觉服务地址（config.json 的 local_api.vision）"""
    try:
        u = str((get_config("./config.json").get("local_api") or {}).get("vision") or "").strip()
        if u:
            return u
    except Exception:
        pass
    try:
        p = int(get_config("./config.json").get("vision_local_port") or 28460)
    except Exception:
        p = 28460
    return f"http://127.0.0.1:{p}/describe"


def vision_fast_size() -> int:
    """「主人正在等」的时候用多大图（越小越快）。

    视觉编码耗时随像素数近似平方增长：1280 → 约 17~20s，896 → 约 6~8s。
    主人主动让你看屏幕时用快速档，别让他等半分钟。
    """
    try:
        return max(280, int(get_config("./config.json").get("vision_fast_max_side") or 896))
    except Exception:
        return 896


def _local_vision_describe(image_path: str, prompt: str = "",
                           max_side: int = 0, max_new: int = 0) -> str:
    """调本机视觉服务（tool/vision_service.py）拿描述。

    max_side/max_new > 0 时按本次调用覆盖（快速档用），0 = 用服务端默认。
    """
    import base64 as _b64
    import urllib.request as _ur
    with open(image_path, "rb") as f:
        img = _b64.b64encode(f.read()).decode()
    body_d = {"image_b64": img, "prompt": prompt}
    if max_side:
        body_d["max_side"] = int(max_side)
    if max_new:
        body_d["max_new"] = int(max_new)
    body = json.dumps(body_d, ensure_ascii=False).encode("utf-8")
    req = _ur.Request(vision_local_url(), data=body,
                      headers={"Content-Type": "application/json"})
    # 本机请求绝不能走系统代理（代理会把 127.0.0.1 也劫走）
    op = _ur.build_opener(_ur.ProxyHandler({}))
    with op.open(req, timeout=300) as r:   # 本地编码一屏要二十多秒，给足时间
        d = json.loads(r.read().decode("utf-8", "ignore"))
    if not d.get("ok"):
        raise RuntimeError(d.get("error") or "本地视觉服务返回失败")
    return str(d.get("text") or "").strip()


def describe_image(image_path: str, prompt: str = "",
                   max_side: int = 0, max_new: int = 0) -> str:
    """统一的「看图说话」入口：按设置走本地视觉模型或云端 API。

    本地服务没起来 / 报错时自动回落到云端（并在日志里说一声），不至于整条链路断掉。
    max_side/max_new：本次调用的快速档参数（主人等着看屏幕时用），0 = 默认。
    """
    if vision_source() == "local":
        try:
            txt = _local_vision_describe(image_path, prompt, max_side=max_side, max_new=max_new)
            if txt:
                print(f"[{now_time()}] [vision-local] 描述完成（{len(txt)} 字）")
                return txt
            print(f"[{now_time()}] [vision-local] ⚠ 空描述 → 回落云端")
        except Exception as e:
            print(f"[{now_time()}] [vision-local] ⚠ 本地视觉不可用（{type(e).__name__}: {e}）→ 回落云端")
    from tool.cloud_API_chat import cloud_vl
    return cloud_vl(image_path)


def _tts_text_lang(text: str) -> str:
    """这段文本该用哪种前端念：ja / zh。

    规则（两条都重要）：
      1) 句子里有假名 → 一定是日语（中文前端念不出假名）
      2) 没有假名（纯汉字，如「了解」「大丈夫」「無理」）→ 跟随当前**语言模式**：
         日语模式（longtext_enabled=false）当日语念，汉语模式当汉语念。
         以前一律按中文念 → 「了解」变成 liǎo jiě，听着就是"日语模式却合成出中文"。
    """
    try:
        if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", str(text or "")):
            return "ja"
    except Exception:
        pass
    try:
        zh_mode = str(get_config("./config.json").get("longtext_enabled", "true")).strip().lower()
        return "zh" if zh_mode in ("true", "1", "yes", "on") else "ja"
    except Exception:
        return "zh"


# 「汉字（假名）」形式的注音：翻日语时为了读音准确会写成这样，
# 但送到 TTS 会被"汉字 + 假名"念两遍 → 只保留括号里的假名。
_PAREN_READING = re.compile(r"([\u4e00-\u9fff]{1,8})[（(]\s*([\u3040-\u309f\u30a0-\u30ffー]+)\s*[）)]")
_KANA_ONLY = re.compile(r"^[\u3040-\u309f\u30a0-\u30ffー]+$")


def _strip_readings(text: str) -> str:
    """把「汉字（かな）」收敛成「かな」，避免同一句话被念两遍。"""
    s = str(text or "")
    if not s or "（" not in s and "(" not in s:
        return s

    def _rep(m):
        kana = m.group(2)
        return kana if _KANA_ONLY.match(kana) else m.group(0)
    try:
        return _PAREN_READING.sub(_rep, s)
    except Exception:
        return s


def _prep_tts_text(sentence: str) -> str:
    """送合成前的统一规整：注音括号收敛 + 首尾空白。"""
    return _strip_readings(sentence).strip()


def _gpt_sovits_service_ready(timeout: float = 1.0) -> bool:
    """探测 TTS 服务是否「真的能用」——注意有两层：

      本机 api.py 代理（配置里的 gpt_sovits_tts，如 http://localhost:28565/tts）
        ↓ 转发
      GPT-SoVITS 本体（local 模式固定 127.0.0.1:9880）

    只探测代理会误判：代理一直在，但本体没启动/还在加载模型时，
    请求会返回 "TTS upstream 请求失败: Cannot connect to host localhost:9880"
    并刷一堆 ERROR 日志（用户实际遇到的就是这个）。
    所以 local 模式下两个端口都要通才算就绪。
    """
    try:
        import socket
        from urllib.parse import urlparse

        def _port_open(host: str, port: int) -> bool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((host, port)) == 0

        # local 模式：只要本机 GPT-SoVITS（9880）在就行 —— 我们直连它，不依赖那个本地代理。
        # （以前要求"代理 + 本体都通"，代理没开就被判定未就绪 → 每句语音都被跳过，只出字不出声）
        try:
            from tool.config import get_config as _gc
            _t = str(_gc("./config.json").get("tts_type") or "local").lower()
        except Exception:
            _t = "local"
        if _t == "local":
            return _port_open("127.0.0.1", 9880)
        # cloud / 代理模式：代理端口通即可
        u = urlparse(gpt_sovits_tts_url)
        return _port_open(u.hostname or "127.0.0.1", u.port or 9880)
    except Exception:
        return False


def _prepare_ref_audio(src_path: str) -> str:
    """
    校验参考音频时长在 3~10 秒内（GPT-SoVITS 硬性要求），合格返回原始文件绝对路径。
    直接发送原始音频（不再生成临时文件，避免跨进程相对路径解析问题）。
    """
    import soundfile as sf

    if not os.path.exists(src_path):
        print(f"[gpt-sovits-tts] ⚠ 参考音频不存在: {src_path}")
        return None
    try:
        info = sf.info(src_path)
    except Exception as e:
        print(f"[gpt-sovits-tts] ⚠ 参考音频读取失败 {src_path}: {e}")
        return None
    dur = info.frames / max(1, info.samplerate)
    if not (3.0 <= dur <= 10.0):
        print(f"[gpt-sovits-tts] ⚠ 参考音频 {os.path.basename(src_path)} 时长 {dur:.2f}s 不在 3~10 秒内，跳过语音合成")
        return None
    return os.path.abspath(src_path)


def _gsv_ensure_pet_model() -> None:
    """确认本机 GPT-SoVITS 加载的是本桌宠的微调权重（否则音色不是她本人）

    launcher 启动的 api_v2 默认就会加载（tts_infer.yaml 的 custom 段），
    但万一被别的实例/别的模型占着 9880，这里补一次 /set_model。
    """
    global _GSV_MODEL_OK
    if _GSV_MODEL_OK:
        return
    _GSV_MODEL_OK = True
    # 默认什么都不做：launcher 启动的 api_v2 本来就会加载桌宠微调权重；
    # 而 /set_model 一旦被调用会重新加载模型（实测一次 100 秒左右），得不偿失。
    # 需要强制指定时才设环境变量 GSV_FORCE_SET_MODEL=1。
    if os.environ.get("GSV_FORCE_SET_MODEL", "").strip() not in ("1", "true", "yes"):
        return
    try:
        from pets.pet_registry import get_pet_config
        v = (get_pet_config().get("voices") or {})
        gpt_rel = str(v.get("gpt_weights") or "").strip()
        sovits_rel = str(v.get("sovits_weights") or "").strip()
        if not (gpt_rel and sovits_rel):
            gpt_rel = "GPT_weights/murasame-gpt.ckpt"
            sovits_rel = "SoVITS_weights/murasame-sovits.pth"
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "GPT-SoVITS")
        gpt = os.path.abspath(os.path.join(base, gpt_rel))
        sovits = os.path.abspath(os.path.join(base, sovits_rel))
        if not (os.path.isfile(gpt) and os.path.isfile(sovits)):
            return
        r = requests.get("http://127.0.0.1:9880/set_model", timeout=6)
        cur = r.text if r.status_code == 200 else ""
        if "murasame" in cur:
            print(f"[{now_time()}] [gpt-sovits-tts] ℹ 已确认加载桌宠微调权重：{os.path.basename(cur[:120])}")
            return
        r2 = requests.get("http://127.0.0.1:9880/set_model",
                          params={"gpt_path": gpt, "sovits_path": sovits}, timeout=180)
        print(f"[{now_time()}] [gpt-sovits-tts] ℹ 指定桌宠微调权重 → HTTP {r2.status_code}")
    except Exception as e:
        print(f"[{now_time()}] [gpt-sovits-tts] ℹ 权重确认跳过：{str(e)[:80]}")


def _gsv_local_direct(text: str, ref_audio: str, prompt_text: str, speed: float, out_path: str) -> bool:
    """直接调用本机 GPT-SoVITS（127.0.0.1:9880），用**旧版参数名**。

    为什么要走这条：配置文件里的 gpt_sovits_tts 是"本地代理"地址，
    而代理不在（或与新版 api.py 参数对不上）时会返回非音频 → 表现为"只出字不出声"。
    本机 api.py 认的是 refer_wav_path / prompt_text / prompt_language / text / text_language。
    """
    import re as _re
    try:
        steps = int(get_config("./config.json").get("gsv_sample_steps", 16))
    except Exception:
        steps = 16

    def _lang_of(t) -> str:
        """判断一段文本该用哪个前端念：带假名 → 日语；否则看当前语言模式。

        ★ 以前这里只看"有没有假名"，于是纯汉字的日语台词（「了解」「大丈夫」
          「無理」这种夏目最常说的短句）被判成中文 → 用中文发音念出来，
          正是用户反馈的"日语模式却合成出中文"。
          现在：没有假名时跟随当前语言模式（日语模式→ja / 汉语模式→zh）。
        """
        return _tts_text_lang(t)

    # ⚠ 两个语言必须分开判断：参考音频是日语 ≠ 要念的句子是日语。
    #   跨语言合成本来就是 GPT-SoVITS 的正常用法：prompt_lang=ja（定音色）+ text_lang=zh（定内容）。
    prompt_lang = _lang_of(prompt_text)
    text_lang = _lang_of(text)
    params = {
        "refer_wav_path": ref_audio,
        "prompt_text": prompt_text or ("こんにちは。" if prompt_lang == "ja" else "你好。"),
        "prompt_language": prompt_lang,
        "text": text,
        "text_language": text_lang,
        "top_k": 15, "top_p": 1, "temperature": 1,
        "speed": speed,
        "sample_steps": steps,
        "if_sr": "false",
    }
    import time as _t
    t0 = _t.time()
    _gsv_ensure_pet_model()                  # 确保是她的微调权重
    data = None
    # ① api_v2：POST /tts（新参数名）—— launcher 启的就是这个
    try:
        p2 = {"text": text, "text_lang": text_lang, "ref_audio_path": ref_audio,
              "prompt_text": params["prompt_text"], "prompt_lang": prompt_lang,
              "top_k": 15, "top_p": 1, "temperature": 1, "text_split_method": "cut0",
              "batch_size": 1, "speed_factor": speed, "streaming_mode": False,
              "parallel_infer": True, "repetition_penalty": 1.35,
              "sample_steps": steps, "super_sampling": False, "media_type": "wav"}
        r = requests.post("http://127.0.0.1:9880/tts", json=p2, timeout=(8, 300))
        if r.status_code == 200 and r.content[:4] == b"RIFF":
            data = r.content
        else:
            print(f"[{now_time()}] [gpt-sovits-tts] ℹ /tts 返回 HTTP {r.status_code}")
    except Exception as e:
        print(f"[{now_time()}] [gpt-sovits-tts] ℹ /tts 失败（{str(e)[:50]}）")
    # ② api.py：GET /（旧参数名）
    if data is None:
        try:
            r = requests.get("http://127.0.0.1:9880/", params=params, timeout=(8, 300))
            if r.status_code == 200 and r.content[:4] == b"RIFF":
                data = r.content
            else:
                print(f"[{now_time()}] [gpt-sovits-tts] ℹ 旧接口返回 HTTP {r.status_code}")
        except Exception as e:
            print(f"[{now_time()}] [gpt-sovits-tts] ℹ 旧接口失败（{str(e)[:50]}）")
    if data:
        try:
            from tool.audio_polish import polish_wav_bytes
            data = polish_wav_bytes(data)              # 统一响度 + 偏闷时提亮
        except Exception:
            pass
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"[{now_time()}] [gpt-sovits-tts] ✅ 本机 GPT-SoVITS 合成成功（{_t.time() - t0:.1f}s）")
        return True
    return False


def gpt_sovits_tts(sentence: str, emotion: str, aux_ref_audio_paths: list = None):
    # ★ 可变默认参数会让「辅助参考音」跨调用累积（2→4→6…），这里改成每次新建副本
    aux_ref_audio_paths = list(aux_ref_audio_paths or [])
    print(f"[{now_time()}] [gpt-sovits-tts] Prompt:{sentence}  {emotion}")

    # 空文本（清理动作描写后可能为空）→ 直接跳过
    if not sentence or not sentence.strip():
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 空文本，跳过语音合成")
        return None
    # 注音括号（「汉字（かな）」）先收敛成假名，别让同一句被念两遍
    sentence = _prep_tts_text(sentence)
    if not sentence:
        return None

    # GPT-SoVITS 服务不可用（未启动 / 模型还在加载 / 绿色版未打包整合包）→ 优雅跳过
    if not _gpt_sovits_service_ready():
        # 只提示一次（每句都刷会淹没有用日志）；提示写清"怎么恢复"
        global _TTS_HINT_SHOWN
        if not _TTS_HINT_SHOWN:
            _TTS_HINT_SHOWN = True
            print(f"[{now_time()}] [gpt-sovits-tts] ⚠ GPT-SoVITS 未就绪（{gpt_sovits_tts_url} → localhost:9880），"
                  f"本次及后续语音将跳过（只说话不出声，不影响聊天）。")
            print(f"[{now_time()}] [gpt-sovits-tts]    · 未启动：在启动器启动桌宠时会自动拉起（GPT-SoVITS 整合包目录）")
            print(f"[{now_time()}] [gpt-sovits-tts]    · 正在加载：模型加载约需 1~2 分钟，就绪后自动恢复发声")
            print(f"[{now_time()}] [gpt-sovits-tts]    · 想关掉语音合成/提示：设置 → 语音合成与识别 → 关闭")
        return None

    # 情感目录从角色语音包动态解析
    from pets.pet_registry import get_pet_config
    pet_cfg = get_pet_config()
    voices_dir = get_short_voices_dir()
    emotion_dirs = get_short_emotion_dirs()
    # 情感不在可用列表中 → 回退到「平静」（若存在）或第一个可用情感
    if not emotion_dirs:
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 当前桌宠无短文本语音包，跳过语音合成")
        return None
    if emotion not in emotion_dirs:
        # 情绪标签拿不到/不合法时的兜底：按人设选「默认情绪」（活泼角色=高兴），
        # 而不是一律回落到「平静」——那正是"语音听着冷淡、没起伏"的根因
        _default = str((pet_cfg.get("voices", {}) or {}).get("default_emotion") or "").strip()
        if _default and _default in emotion_dirs:
            emotion = _default
        elif "高兴" in emotion_dirs:
            emotion = "高兴"
        elif "平静" in emotion_dirs:
            emotion = "平静"
        else:
            emotion = emotion_dirs[0]
        print(f"[gpt-sovits-tts] ℹ️ 情绪标签不可用 → 按人设使用「{emotion}」参考音频")

    # 情绪是否换"参考录音"：默认换（更有情绪）；想彻底统一音色就把 gsv_emotion_refs 设为 false，
    # 这样永远用同一个参考，只靠语速体现情绪。
    try:
        _use_emo_ref = str(get_config("./config.json").get("gsv_emotion_refs", True)).lower() not in ("false", "0", "no")
    except Exception:
        _use_emo_ref = True
    if not _use_emo_ref:
        _dflt = str((pet_cfg.get("voices", {}) or {}).get("default_emotion") or "").strip()
        if _dflt and _dflt in emotion_dirs:
            emotion = _dflt
        elif "平静" in emotion_dirs:
            emotion = "平静"
        elif emotion_dirs:
            emotion = emotion_dirs[0]

    emotion_path = os.path.join(voices_dir, emotion)
    if not os.path.isdir(emotion_path):
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 情感目录不存在: {emotion_path}，跳过语音合成")
        return None

    audio = os.listdir(emotion_path)
    # 只保留音频文件（过滤 asr.txt / README.txt 等非音频文件）
    audio = [a for a in audio if a.lower().endswith((".wav", ".mp3", ".flac", ".ogg"))]
    # 情感目录没有音频文件 → 优雅跳过（避免 IndexError: list index out of range）
    if not audio:
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 情感目录 '{emotion}' 无音频文件，跳过语音合成")
        return None
    if tts_type == "local":
        # 本地模式：时长校验（3~10s）后发送原始音频绝对路径（与丛雨历史行为一致）
        path = os.path.abspath(os.path.join(emotion_path, audio[0]))
        ref_path = _prepare_ref_audio(path)
        if ref_path is None:
            return None
        path = ref_path
        # ★ 同一情感目录里的其它音频 → 作为「辅助参考音」一起发给 GPT-SoVITS，
        #   多参考能让音色更稳、更像本人（用户要求：多挑几条参考音）
        try:
            _aux_all = sorted(a for a in audio if a != audio[0])
            for _a in _aux_all:
                _ap = _prepare_ref_audio(os.path.abspath(os.path.join(emotion_path, _a)))
                if _ap and _ap not in aux_ref_audio_paths:
                    aux_ref_audio_paths.append(_ap)
            if aux_ref_audio_paths:
                print(f"[{now_time()}] [gpt-sovits-tts] 辅助参考音 {len(aux_ref_audio_paths)} 条")
        except Exception as _e:
            print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 辅助参考音收集失败: {_e}")
    elif tts_type == "cloud":
        path = f"/root/reference_voices/{emotion}/{audio[0]}"
    with open(os.path.join(emotion_path, "asr.txt"), "r", encoding="utf-8") as f:
        ref = f.read().strip()

    # 语速按情绪微调（活泼人设：高兴/着急说得快一点更有元气；害羞稍慢）
    # 角色包 pet.json 的 voices.emotion_speed 可覆盖默认值
    _SPEED_DEFAULT = {"高兴": 1.08, "着急": 1.10, "惊讶": 1.06,
                      "生气": 1.05, "害羞": 0.96, "平静": 1.0}
    try:
        _speed_map = dict(_SPEED_DEFAULT)
        _speed_map.update({str(k): float(v) for k, v in
                           ((pet_cfg.get("voices", {}) or {}).get("emotion_speed") or {}).items()})
    except Exception:
        _speed_map = _SPEED_DEFAULT
    _speed = float(_speed_map.get(emotion, 1.0))
    params = {
        "text": sentence,
        "text_lang": _tts_text_lang(sentence),
        "ref_audio_path": path,
        "aux_ref_audio_paths": aux_ref_audio_paths,
        "prompt_text": ref,
        "prompt_lang": _tts_text_lang(ref),
        "top_k": 15,
        "top_p": 1,
        "temperature": 1,
        "text_split_method": "cut1",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,
        "speed_factor": _speed,
        "streaming_mode": False,
        "seed": -1,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
        "sample_steps": 32,
        "super_sampling": False
    }

    # 本地模式：优先直连本机 GPT-SoVITS（旧版参数名）—— 代理不在时这是唯一能出声的路径
    if tts_type == "local":
        import hashlib as _hl
        # 缓存指纹里带上"参考音频的指纹 + 当前模型名"：换了音色/模型，旧缓存自动作废
        _fp = ""
        try:
            _st = os.stat(path)
            _fp = "%d_%d" % (int(_st.st_mtime), int(_st.st_size))
        except Exception:
            pass
        _model = ""
        try:
            # 只读本地权重文件的指纹（绝不调 /set_model —— 那会重新加载模型，一次上百秒）
            from pets.pet_registry import get_pet_config
            _v = (get_pet_config().get("voices") or {})
            _gsv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "GPT-SoVITS")
            for _rel in (str(_v.get("gpt_weights") or "GPT_weights/murasame-gpt.ckpt"),
                         str(_v.get("sovits_weights") or "SoVITS_weights/murasame-sovits.pth")):
                _fp2 = os.path.abspath(os.path.join(_gsv, _rel))
                if os.path.isfile(_fp2):
                    _st2 = os.stat(_fp2)
                    _model += "%s@%d_%d;" % (os.path.basename(_fp2), int(_st2.st_mtime), int(_st2.st_size))
        except Exception:
            pass
        # 缓存键必须包含"一切影响音频的参数"：参考音频、情绪、语速、模型……
        # 以及**合成语言**和 CACHE_VER。少了语言这一项时，改语言参数后旧音频仍被复用，
        # 表现为"明明修好了，听着还是老样子"（中文台词照旧是日文念的）。
        _lang_key = _tts_text_lang(sentence)
        _key = _hl.md5(("%s|%s|%s|%.2f|%s|%s|%s|%s"
                        % (sentence, path, emotion, _speed, _fp, _model,
                           _lang_key, CACHE_VER)).encode("utf-8")).hexdigest()
        os.makedirs("./tmp", exist_ok=True)
        _cache = os.path.join("./tmp", "tts_cache", _key + ".wav")
        _out = os.path.join("./tmp", _key + ".wav")
        try:
            if os.path.isfile(_cache) and os.path.getsize(_cache) > 1000:
                import shutil as _sh
                _sh.copy2(_cache, _out)          # 同一句重复说 → 直接复用，0 延迟
                print(f"[{now_time()}] [gpt-sovits-tts] ⚡ 命中缓存（{emotion}）")
                return _key
        except Exception:
            pass
        if _gsv_local_direct(sentence, path, ref, _speed, _out):
            try:
                import shutil as _sh
                os.makedirs(os.path.dirname(_cache), exist_ok=True)
                _sh.copy2(_out, _cache)
                _cd = os.path.dirname(_cache)
                for _f in os.listdir(_cd):       # 缓存别无限涨：3 天前的删掉
                    _fp = os.path.join(_cd, _f)
                    try:
                        if os.path.getmtime(_fp) < time.time() - 86400 * 3:
                            os.remove(_fp)
                    except Exception:
                        pass
            except Exception:
                pass
            return _key

    try:
        # 显式超时：TTS 合成可能较慢（音频生成），但绝不能无限挂起阻塞线程
        reply = requests.post(gpt_sovits_tts_url, json={"params": params},
                              timeout=(15, 300))
    except Exception as e:
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 请求失败（跳过语音）: {e}")
        return None

    # 判定返回是否为音频，否则打印错误与详细信息并跳过写入
    content_type = reply.headers.get("Content-Type", "")
    if not content_type.startswith("audio/"):
        status = getattr(reply, "status_code", "?")
        detail_str = ""
        err_msg = None
        try:
            data = reply.json()
            err_msg = data.get("error") or data.get("message")
            # 打印完整 JSON 详情（去除 ASCII 转义）
            detail_str = json.dumps(data, ensure_ascii=False)
        except Exception:
            text_body = getattr(reply, "text", "")
            if not text_body:
                text_body = f"unexpected content-type: {content_type}"
            # 截断过长文本，避免刷屏
            detail_str = (text_body[:2000] + "…") if len(text_body) > 2000 else text_body
        err_msg = err_msg or ""
        print(f"[{now_time()}] [gpt-sovits-tts][ERROR] HTTP {status} - {err_msg} | detail: {detail_str}")
        return None

    # 写入 tmp 临时目录（播放后删除，不长期缓存）
    os.makedirs("./tmp", exist_ok=True)
    sentence_md5 = hashlib.md5(sentence.encode()).hexdigest()
    out_path = f"./tmp/{sentence_md5}.wav"
    with open(out_path, "wb") as f:
        f.write(reply.content)
    print(f"[{now_time()}] [gpt-sovits-tts] Wav_name:{sentence_md5}")
    return sentence_md5


# 形如「某某：台词」的行（说话人名字不在名单里时用它兜底判断剧本续写）
_SCRIPT_LINE = re.compile(r"^\s{0,3}[\w\u4e00-\u9fff]{1,8}\s*[:：]\s*\S")


def _speaker_label_re():
    """构造「说话人标签」正则：user/assistant/system、主人，以及所有桌宠的名字。

    标签还可能是叠写的（「user主人：…」），结尾可能是冒号，也可能是 JSON 的 [
    （模型续写自己的台词时会写成 assistant["…"] 这种形式）。
    名字按长度倒序拼进正则，避免「四季夏目」被「夏目」抢先匹配。
    """
    names = ["user", "assistant", "system", "主人", "将臣", "凉水"]
    try:
        from pets import pet_registry as _pr
        for _pid in _pr.get_pet_ids():
            _cfg = _pr.get_pet_config(_pid) or {}
            for _key in ("name", "display_name"):
                _v = str(_cfg.get(_key) or "").strip()
                if _v:
                    names.append(_v)
    except Exception:
        names += ["夏目", "丛雨", "诺瓦"]
    uniq = sorted({n for n in names if n}, key=len, reverse=True)
    name_re = "|".join(re.escape(n) for n in uniq)
    tail = r"(?:\s*(?:" + name_re + r"))?\s*[:：\[]"
    head = re.compile(r"^[\s\"'（(【\[]{0,4}(?:" + name_re + r")" + tail, re.I)
    inline = re.compile(r"[\s。！？…，,；;、\"'）)】](?:" + name_re + r")" + tail, re.I)
    return head, inline


def strip_self_dialogue(text):
    """去掉模型自己续写的「主人：…」「user主人：…」「assistant["…"]」多轮剧本。

    现象（用户反馈「AI 自问自答」）：模型把记忆里的历史当成剧本继续往下写，
    返回里带着主人的台词和下一轮自己的台词，桌宠就会把主人的话也一起念出来。
    处理：遇到说话人标签就截断——行首标签丢弃该行及其后全部内容，行内标签只截断该行；
    万一标签是这样的格式但说话人名字不在名单里，还会有一次「两行以上『某某：台词』」的兜底判断。
    """
    s = str(text or "")
    if not s:
        return s
    head, inline = _speaker_label_re()
    out = []
    for ln in s.splitlines():
        if head.match(ln):
            break
        m = inline.search(ln)
        if m:
            ln = ln[:m.start() + 1].rstrip()   # +1：保留标签前的标点
        if ln.strip():
            out.append(ln)
    # 兜底：正文里还留着两行以上「某个名字：台词」，基本能断定是剧本，从第一行起截掉
    labelled = [i for i, ln in enumerate(out) if _SCRIPT_LINE.match(ln)]
    if len(labelled) >= 2:
        out = out[:labelled[0]]
    r = "\n".join(out).strip()
    return r if r else s
