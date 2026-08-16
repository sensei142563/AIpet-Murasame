import base64
import json
import hashlib
import os
from datetime import datetime

import requests

from tool.config import get_config
from tool.time_utils import build_time_context
from pets.pet_registry import get_short_emotion_dirs, get_short_voices_dir, get_short_emotions


def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now

ollama_url = get_config("./config.json")["local_api"]["ollama"]
qwen3_lora_url = get_config("./config.json")["local_api"]["qwen3_lora"]
gpt_sovits_tts_url = get_config("./config.json")["local_api"]["gpt_sovits_tts"]
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
    reply = requests.post(ollama_url, json={"prompt": prompt, "headers": headers})
    reply = reply.json()
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

    # 2. 高权重「最近的观察」（识别触发的内容，仅本轮有高权重）
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

    # 3. 正常对话历史
    messages.extend(filtered_history)

    time_ctx = build_time_context()
    if role != "system":
        user_input = f"[{time_ctx}]{user_input}"
        history.append({"role": role, "content": user_input})
        messages.append({"role": role, "content": user_input})
    else:
        messages.append({"role": role, "content": user_input})
    print(f"[{now_time()}] [qwen3-lora] Prompt:{messages}")
    reply = requests.post(qwen3_lora_url, json={"history": messages})
    reply = reply.json()
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

def ollama_qwen3_portrait(sentence: str, history: list, type):
    # ===== 从角色包读取立绘映射（无则回退通用提示）=====
    from pets.pet_registry import get_portrait_prompts
    portrait_cfg = get_portrait_prompts()
    set_cfg = portrait_cfg.get("sets", {}).get(type, {})
    if set_cfg:
        template = portrait_cfg.get("prompt_template", "")
        sysprompt = template.replace("{layers_desc}", set_cfg.get("layers_desc", "")) \
                            .replace("{example}", set_cfg.get("example", ""))
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
    outfit_hint = f"（保持衣服连贯：上次使用的基础人物 ID 为 {outfit_id}，本次请沿用同款衣服）" if outfit_id else "（无历史，自由选衣服）"

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
    labels = '，'.join(emotion_dirs) if emotion_dirs else '平静'
    if emotion_dirs:
        example = f'如["{emotion_dirs[0]}", "{emotion_dirs[1] if len(emotion_dirs) > 1 else emotion_dirs[0]}"]'
    else:
        example = '如["平静", "平静"]'
    identity = f"你是一个情感分析助手，负责分析“{pet_name}”说的话的情感。你现在需要将用户输入的句子进行分析，综合用户的输入和{pet_name}的输出返回一个{pet_name}最新一句话每个分句情感的标签。你只可以选择的标签有{labels}。你需要直接返回一个情感列表，不需要其他任何内容。{example}/no_think"
    history_l = history[1:]
    prompt = {"model": "qwen3:14b",
              "prompt": f"{identity}   历史：{history_l}",
              "stream": False}
    reply = ollama_post("ollama-qwen3-emotion", prompt)
    return reply

def ollama_qwen25vl(image_path: str):
    identity = "你现在要担任一个AI桌宠的视觉识别助手，我会向你提供用户此时的屏幕截图和历史记录，你要详细描述屏幕内容与使用的软件，描述页面主题。我会将你的描述以system消息提供给另外一个处理语言的AI模型。   "
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = {"model": "qwen2.5vl:7b",
              "prompt": f"{identity} 现在描述用户的行为。 ",
              "images": [img_b64],
              "stream": False}
    reply = ollama_post("ollama-qwen2.5vl", prompt)
    return reply

def _gpt_sovits_service_ready(timeout: float = 1.0) -> bool:
    """探测 GPT-SoVITS HTTP 服务是否可用（避免连接失败刷 traceback）"""
    try:
        import socket
        from urllib.parse import urlparse
        u = urlparse(gpt_sovits_tts_url)
        host = u.hostname or "127.0.0.1"
        port = u.port or 9880
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
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


def gpt_sovits_tts(sentence: str, emotion: str, aux_ref_audio_paths: list = []):
    print(f"[{now_time()}] [gpt-sovits-tts] Prompt:{sentence}  {emotion}")

    # 空文本（清理动作描写后可能为空）→ 直接跳过
    if not sentence or not sentence.strip():
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 空文本，跳过语音合成")
        return None

    # GPT-SoVITS 服务不可用（未启动 / 绿色版未打包整合包）→ 优雅跳过，不崩溃
    if not _gpt_sovits_service_ready():
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ GPT-SoVITS 服务不可用（{gpt_sovits_tts_url}），跳过语音合成")
        return None

    # 情感目录从角色语音包动态解析
    voices_dir = get_short_voices_dir()
    emotion_dirs = get_short_emotion_dirs()
    # 情感不在可用列表中 → 回退到「平静」（若存在）或第一个可用情感
    if not emotion_dirs:
        print(f"[{now_time()}] [gpt-sovits-tts] ⚠ 当前桌宠无短文本语音包，跳过语音合成")
        return None
    if emotion not in emotion_dirs:
        emotion = "平静" if "平静" in emotion_dirs else emotion_dirs[0]

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
    elif tts_type == "cloud":
        path = f"/root/reference_voices/{emotion}/{audio[0]}"
    with open(os.path.join(emotion_path, "asr.txt"), "r", encoding="utf-8") as f:
        ref = f.read().strip()
    params = {
        "text": sentence,
        "text_lang": "ja",
        "ref_audio_path": path,
        "aux_ref_audio_paths": aux_ref_audio_paths,
        "prompt_text": ref,
        "prompt_lang": "ja",
        "top_k": 15,
        "top_p": 1,
        "temperature": 1,
        "text_split_method": "cut1",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,
        "speed_factor": 1.0,
        "streaming_mode": False,
        "seed": -1,
        "parallel_infer": True,
        "repetition_penalty": 1.35,
        "sample_steps": 32,
        "super_sampling": False
    }

    reply = requests.post(gpt_sovits_tts_url, json={"params": params})

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
