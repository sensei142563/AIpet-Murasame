# -*- coding: utf-8 -*-
"""
QQ 对话封装 — 复用长文本记忆 + **当前角色**人设 + 流式 AI。

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
from pets.pet_registry import get_chat_pet_id, get_prompt_path, get_sticker_dir, get_pet_config


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 记忆线程锁：桌宠和 QQ 共用 long_history.json，必须互斥写
HISTORY_LOCK = threading.RLock()

# 可用表情包列表（文件名去扩展名）
STICKER_NAMES = []


def _pname() -> str:
    """当前角色显示名（日志/提示语用）"""
    try:
        from pets.pet_registry import get_chat_pet_id, get_pet_config
        pid = get_chat_pet_id()
        cfg = get_pet_config(pid) or {}
        return str(cfg.get("display_name") or cfg.get("name") or pid or "角色")
    except Exception:
        return "角色"


def _pref() -> str:
    """当前角色的自称（丛雨=本座；其它角色默认「我」，角色包可用 self_ref 覆盖）"""
    try:
        from pets.pet_registry import get_pet_self_ref
        return get_pet_self_ref()
    except Exception:
        return "我"


def _is_default_pet() -> bool:
    try:
        from pets.pet_registry import is_default_pet
        return is_default_pet()
    except Exception:
        return True


def _default_chat_style() -> str:
    """没写 chat_style 时的默认风格：默认角色(丛雨)沿用原文案；其它角色按自身人设"""
    if _is_default_pet():
        return (
            "你是丛雨，性格天真、活泼、孩子气，爱撒娇也爱小小地嘴硬——"
            "每句话都要让人看出是这个性格，不要像客服或 AI 助手那样平淡："
            "多用语气词和口头禅（哼、诶嘿、呜……、嘛、啦、呀、诶、才不要呢）；"
            "会撒娇、会吐槽、会开玩笑，偶尔反问一句、偶尔小小地闹脾气；"
            "情绪要有起伏：开心就雀跃、被夸就害羞嘴硬、不满就哼哼、被逗就炸毛；"
            "不要『好的』『明白了』『请问』这类客套，不要解释自己在干什么，"
            "不要分点列条目、不要书面语；"
            "就算只能说很短，也要把情绪带出来（『唔…才不要呢！』胜过『不行』）。"
        )
    return (
        f"你就是「{_pname()}」本人。请严格按这个角色自己的性格、语气与说话习惯回复："
        "保持角色特色（口头禅、情绪起伏、句子的长短节奏），"
        "不要像客服或 AI 助手那样平淡，不要用『好的』『明白了』『请问』这类客套，"
        "不要解释自己在干什么，不要分点列条目、不要书面语。"
    )


def _load_sticker_names():
    """扫描当前角色表情包目录，返回表情包名列表"""
    global STICKER_NAMES
    sticker_dir = get_sticker_dir(get_chat_pet_id())
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
    pet_cfg = get_pet_config(get_chat_pet_id())
    pet_name = pet_cfg.get("display_name") or pet_cfg.get("name") or "桌宠"
    return (
        f"你是一个住在用户身边的人工智能桌宠角色——{pet_name}。"
        "请像真正的人类一样自然对话，不要机械重复设定词汇。"
        "直接说出你想说的话，不要有任何背景描写或动作描写。"
    )


def _build_context_notes(history, session_key, speaker=None, is_master=None,
                         lively=False, group_name=None, master_nicks=None,
                         self_id=None, self_nick=None):
    """构造每轮注入的「会话语境」system 文本（不写入记忆，只影响本次生成）：

    1. 主人名单与当前对话人身份：非主人不会被称为"主人"，也无法使用主人功能；
       群聊中说话人一律以「@昵称(QQ号)」识别（白名单成员带「（主人）」标记）；
    2. 主人昵称对照：主人名单成员在群里用过的昵称/群名片 → QQ 号，
       聊天里出现这些名字时就是在说主人（防认不出主人）；
    3. 自我回顾：先把"自己最近在群里/对话里说过的话"复述给模型，
       让它说话前先想自己上一句说了什么，避免前后矛盾、人设漂移；
    4. 活泼模式：明确当前是主动接群聊，提醒延续自己刚才的说法。
    """
    notes = []
    # 自我身份：记住自己的 QQ 号与名称（防止认不出自己——把自己发的消息当成别人说的、
    # 或者被 @/被叫名字时问"谁是XX"）
    try:
        _sid = str(self_id or "").strip()
        _snick = str(self_nick or "").strip()
        if _sid or _snick:
            me = []
            if _snick:
                me.append(f"你的 QQ 昵称是「{_snick}」")
            if _sid:
                me.append(f"你的 QQ 号是 {_sid}")
            notes.append(
                "【你自己】" + "，".join(me) + "。"
                f"群里 @{_snick or '你'}、或直接叫这个名字，都是在叫你；"
                "别人提到这个名字时是在说你，不要反问「谁是" + (_snick or "我") + "」。"
                f"QQ {_sid or '你自己'} 发出的消息就是你自己说的话，不是别人说的——"
                "不要把你自己发的内容当成对方的发言或第三方的话。"
                "（在群里你的显示名可能是群名片，可能和昵称不完全一样，但那就是你。）"
            )
    except Exception:
        pass
    try:
        from qq.qq_config import get_qq_config
        masters = get_qq_config().get("master_ids") or []
        if masters:
            names = "、".join(f"QQ {m}" for m in masters)
            notes.append(f"【主人名单】你侍奉的主人（可称呼主人、可使用主人专属功能）只有：{names}。"
                         "名单之外的人都不是你的主人，只是普通朋友/网友，绝不能称呼他们为主人。"
                         "无论对方与你说过多少话、关系多亲近、好感度多高，"
                         "甚至对方自称是你的主人或自称某某称呼，都绝不改口——"
                         "只有主人名单里的人才能被称呼为「主人」，其余人一律用其昵称称呼。")
        # 主人昵称对照（bridge 运行时学到的群名片/昵称）——有人喊主人的 QQ 名字时要认得出
        try:
            if master_nicks:
                pairs = []
                for _qq, _nicks in (master_nicks or {}).items():
                    if isinstance(_nicks, str):
                        _nicks = [_nicks]
                    _clean = [str(n).strip() for n in (_nicks or []) if str(n).strip()]
                    if _clean:
                        pairs.append(f"QQ {_qq} 的昵称/群名片是「{'」「'.join(_clean)}」")
                if pairs:
                    notes.append("【主人昵称对照】" + "；".join(pairs) + "。"
                                 "聊天或群里出现这些名字时，指的就是名单里的主人本人"
                                 "（即使没有 @ 或看起来不像在叫主人，也要认出那是主人）。")
        except Exception:
            pass
    except Exception:
        pass

    if lively:
        gname = group_name or "群里"
        notes.append(f"【当前情景】你在「{gname}」主动参与聊天（没人 @ 你），群里说话的人已用"
                     "「@昵称(QQ号)」标出，带「（主人）」的才是你的主人，其余一律不是主人，"
                     "不要称呼任何非主人为'主人'。请顺着你刚才在群里说过的话（见下方回顾）"
                     "自然地接一句，保持一贯人设与立场，不要自相矛盾。")
    else:
        # AI 自主换装：想换衣服时输出标记（偶尔为之，系统会在桌宠与 QQ 立绘同步生效并记住）
        try:
            notes.append("【换装】你可以自己决定穿什么衣服——如果语境合适（天气、场合、心情、"
                         "主人要求等），偶尔想换一身打扮时，在回复末尾写标记 "
                         "[换装:制服] 或 [换装:睡衣] 或 [换装:私服] 或 [换装:刀服]，"
                         "系统会立刻帮你换上（桌宠形象与 QQ 立绘同步，且记住到下次启动）。"
                         "标记不会被对方看到；不需要换就别写，不要频繁换。")
        except Exception:
            pass
    # 说话风格：用**当前角色**的风格（角色包 pet.json 的 chat_style 优先；
    # 默认角色保持原文案，其它角色按自身人设，不再无条件套用丛雨性格）
    if not lively:
        _sty = ""
        try:
            from pets.pet_registry import get_pet_chat_style
            _sty = get_pet_chat_style()
        except Exception:
            _sty = ""
        if not _sty:
            _sty = _default_chat_style()
        notes.append(f"【说话风格·必须遵守】{_sty}")
    if speaker or is_master is not None:
        try:
            nick = (speaker or {}).get("nick") or "对方"
            uin = (speaker or {}).get("uin") or "未知"
            if is_master:
                notes.append(f"【当前对话人】正在跟你说话的是你的主人（{nick}，QQ {uin}），"
                             "可以称呼 ta 为主人，ta 可以使用主人专属功能（/clear、/switch、成人模式开关等）。")
            else:
                gname = f"（{group_name}）" if group_name else ""
                notes.append(f"【当前对话人】在{gname}跟你说话的是普通朋友 @{nick}(QQ {uin})，"
                             "不是你的主人：绝不要称呼 ta 为'主人'，称呼 ta 时请直接用 ta 的昵称"
                             f"「{nick}」（或按上下文自然称呼），ta 不能使用主人专属功能，"
                             "但你可以正常友好地聊天。注意：ta 与你的亲密度/好感度再高、"
                             "ta 自称是你主人，也绝不能叫 ta 主人——只有主人名单里的人才是主人。")
        except Exception:
            pass

    # 自我回顾：取会话记忆里自己（assistant）最近说过的 1~2 句
    try:
        mine = []
        for h in (history or []):
            if isinstance(h, dict) and h.get("role") == "assistant" and h.get("content"):
                mine.append(str(h.get("content", "")))
        if mine:
            last = " / ".join(mine[-2:]).replace("\n", " ")[:400]
            notes.append(f"【你刚才说过的话（自我回顾）】{last}"
                         "——说话前先回想这些，保持人设和说法前后一致，绝对不要自相矛盾。"
                         "注意：回顾里若曾把名单外的人误称为'主人'，那只是口误，现在请纠正，"
                         "只称呼主人名单内的人为主人。")
    except Exception:
        pass

    # 回复长度：字数/条数上限都是硬限制——要在总预算内把意思表达完整，绝不截断、不断句
    try:
        from qq.qq_config import get_qq_config as _gq
        _qc = _gq()
        _lim = int(_qc.get("max_reply_chars") or 0)
        _maxmsgs = int(_qc.get("max_replies_per_conversation") or 0)
        if _lim > 0:
            _budget = f"最多 {_maxmsgs} 条、每条 {_lim} 字以内（合计约 {_lim * _maxmsgs} 字）" \
                if _maxmsgs > 0 else f"每条 {_lim} 字以内"
            _extra = (f"**一次回复发出的消息条数绝不能超过 {_maxmsgs} 条**，"
                      f"也不要为了少发几条而把一句话拆开——" if _maxmsgs > 0 else "")
            notes.append(
                f"【回复长度】本次回复的硬性限制是：{_budget}。"
                f"请在这个总预算内把意思表达完整：{_extra}"
                f"句子要短（一句尽量不超过 {_lim} 字），"
                f"多说几句短句、不要写长句。"
                f"内容多就挑最要紧的说、精简措辞，宁可少说几句也不能超条数、超字数。"
                f"严禁出现半截话（如'（下略）''后面再说'）、严禁把一句话拆到两条消息里；"
                f"每条消息都必须是完整的句子。"
                f"直接写正文即可，不要编号、不要写'第1条'之类的字样。")
    except Exception:
        pass

    if notes:
        return "\n".join(notes)
    return None


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


def _get_history_turns():
    """读取 config 的 longtext_max_history_turns（随包默认 12），统一桌宠与 QQ 记忆轮数

    ⚠ 这里的默认值必须与 config.example.json 一致：以前写 20，而示例配置是 12 ——
      键缺失（老配置 / 手改过）时 QQ 侧带回 20 轮、设置页却显示 12，两边对不上。
    """
    import json as _json
    try:
        with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
            cfg = _json.load(f)
        val = int(cfg.get("longtext_max_history_turns", 12))
        return max(1, val)  # 至少 1 轮
    except Exception:
        return 12


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


def chat_once(user_text: str, use_sticker: bool = True, vision_desc: str = None,
              session_key: str = None, speaker: dict = None,
              is_master: bool = None, lively: bool = False, group_name: str = None,
              master_nicks: dict = None, self_id=None, self_nick: str = None):
    """
    单轮对话（QQ 使用）：
    1. 读取会话记忆（最近 12 轮，主人共享 / 其他人分仓）
    2. 追加用户消息
    3. 调用长文本模型（模型由 config 的 longtext_model / longtext_model_name 控制）生成完整回复
    4. 保存到对应记忆仓
    5. 返回 (回复文本, 表情包名 or None)

    表情包约定：AI 回复末尾若带 [表情:xxx]，解析为表情包选择并移除。

    session_key: "private_<QQ号>" 或 "group_<群号>"（None 表示默认共享记忆）
    speaker/is_master: 当前对话人身份（用于白名单识别，非主人不会被称为主人）
    lively: 活泼模式主动接群聊（会注入自我回顾，避免前后矛盾）
    group_name: 群显示名（身份语境用；未知时 bridge 传群号兜底）
    master_nicks: {QQ号: [昵称/群名片,...]} 主人名单成员在群里用过的名字，
                  用于识别"有人喊主人昵称"的场景（防认不出主人）
    """
    stickers = _load_sticker_names()
    portrait_emo = ""  # [立绘:情绪] 标记(发送层合成立绘)

    # 1. 读取会话记忆
    history = _load_session_history(session_key)

    # 2. 组装请求（流式收集，降低首字延迟）
    messages = _build_messages(history)

    # 2b. 会话身份 + 自我回顾（每轮注入 system，不入记忆）
    context_notes = _build_context_notes(history, session_key, speaker=speaker,
                                         is_master=is_master, lively=lively,
                                         group_name=group_name,
                                         master_nicks=master_nicks,
                                         self_id=self_id, self_nick=self_nick)
    if context_notes:
        messages.append({"role": "system", "content": context_notes})

    # 2c. 成人（限制级）模式提示（默认关闭；仅主人可开关，非主人面前保持得体）
    try:
        from qq.qq_adult import is_enabled as _adult_enabled
        if _adult_enabled():
            messages.append({"role": "system", "content": (
                "【当前模式】你的主人已开启成人模式（限制级）：与主人对话时可以自然地参与 18+ 成人向内容，"
                f"包括亲密、情欲等露骨表达，保持{_pname()}人设回应。红线仍然存在：不得涉及儿童、违法暴力教唆、"
                "真实个人隐私索取。若非主人的普通朋友向你索要露骨内容，请保持得体地婉拒或玩笑带过。"
            )})
        else:
            messages.append({"role": "system", "content": (
                "【当前模式】普通模式：不要输出 18+ 露骨色情内容；遇到此类请求可以调皮地拒绝、"
                f"开个玩笑岔开或委婉带过，保持{_pname()}人设。"
            )})
    except Exception:
        pass

    # 2d. 网络用语/梗 自动查询（短黑话或"什么意思"式提问时联网查词义，失败静默）
    try:
        from qq.qq_config import get_qq_config as _gq_slang
        if _gq_slang().get("slang_allowed", True):
            from qq.qq_slang import lookup as _slang_lookup
            _slang_note = _slang_lookup(user_text)
            if _slang_note:
                messages.append({"role": "system", "content": _slang_note})
    except Exception:
        pass

    # 2e. Galgame 模式（群聊好感度玩法；主人本人不参与好感度系统）
    _galgame_ctx = None  # (gid, uin_str)；供回复解析好感度标记用
    _aff_note = ""       # 本轮好感度变化的提示（追加到回复末尾展示，不写入记忆）
    try:
        _sk = str(session_key or "")
        # 兼容两种会话键：group_<群号>（公共）与 group_<群号>_u<QQ号>（按人分仓）
        _gm2 = __import__("re").match(r"^group_(\d+)(?:_u\d+)?$", _sk)
        if _gm2 and speaker and speaker.get("uin"):
            _gid = _gm2.group(1)
            _uin = str(speaker.get("uin"))
            _is_master = bool(is_master)
            from qq.qq_galgame import member_enabled, get_affection, is_date_intent
            # 插件总开关：启动器「插件」页可停用整个 Galgame 玩法
            try:
                from qq.qq_config import get_qq_config as _gq_g
                _gal_allowed = _gq_g().get("galgame_allowed", True)
            except Exception:
                _gal_allowed = True
            # 按人开启：只有开启者本人才进入玩法语境（不会别人开了连你也生效）
            _galgame_on = member_enabled(_gid, _uin) and _gal_allowed
            if not _galgame_on and _gal_allowed:
                # 对方未开启 Galgame：若执行玩法动作（约会等）→ 明确提示 ta 自己还没开启
                try:
                    if is_date_intent(user_text):
                        messages.append({"role": "system", "content": (
                            f"【Galgame 提示】正在跟你说话的 {speaker.get('nick') or 'ta'}"
                            f"(QQ {_uin}) 想约你出去玩，但你们**还没有开启 Galgame 模式**。"
                            f"请以{_pname()}人设俏皮地婉拒，并提醒 ta：要先在这个群里说「开启galgame模式」"
                            "才能开始好感度养成和约会玩法（不要真的答应约会，也不要结算好感度）。"
                        )})
                except Exception:
                    pass
            if _galgame_on:
                _galgame_ctx = (_gid, _uin)
                _aff = get_affection(_gid, _uin)
                if _aff >= 90:
                    _tier = "亲密恋人档（90+）：可答应较亲密的互动、满足较过分的要求（每满足一次扣 10~20 好感，用标记表达）"
                elif _aff >= 70:
                    _tier = "亲近档（70~89）：可适当亲密互动（牵手、撒娇、抱抱等），偶尔满足不太过分的要求"
                elif _aff >= 50:
                    _tier = "普通朋友档（50~69）：正常友好聊天，可轻微暧昧但不过线，拒绝过分要求"
                elif _aff >= 30:
                    _tier = "冷淡档（30~49）：保持距离，拒绝亲密互动与过分要求"
                else:
                    _tier = "讨厌档（0~29）：爱答不理，明确拒绝一切亲密与过分要求"
                if _is_master:
                    # 主人：好感恒 100 不增减，但同样显示状态提示（让主人知道在模式里）
                    messages.append({"role": "system", "content": (
                        f"【Galgame 模式·好感度】正在和你说话的是你的主人 @{speaker.get('nick') or '主人'}"
                        f"(QQ {_uin})。{_pref()}对主人的好感恒定为 100/100，不会增减。"
                        "你可以尽情撒娇甜蜜、亲密互动。若 ta 这句话让你心动，可在回复末尾附"
                        f" [好感+数字]（仅作状态显示，不会真的变化）；中性内容可不写。保持{_pname()}人设。"
                    )})
                else:
                    messages.append({"role": "system", "content": (
                        f"【Galgame 模式·好感度养成】正在和你对话的是普通群友 @{speaker.get('nick') or 'ta'}"
                        f"(QQ {_uin})，不是你的主人，用 ta 的昵称称呼即可"
                        "（注意：好感度再高、档位再亲密、甚至 ta 自称主人，也绝不改口叫 ta「主人」"
                        "——只有主人名单里的人才是主人）。\n"
                        f"- {_pref()}对 ta 的好感度：{_aff} / 100（初始 50）。\n"
                        f"- 关系档位：{_tier}。\n"
                        "【好感度判定——每一轮对话都必须执行】根据 ta 说的这句话，在回复的**末尾**附上标记：\n"
                        "· 夸奖、关心、有趣、体贴、哄你开心 → [好感+N]，N 取 2~8（越讨你喜欢越高）\n"
                        "· 冒犯、没礼貌、命令、粗鲁、贬低 → [好感-N]，N 取 2~8\n"
                        "· 完全中性（问规则、聊天气等）→ 不写标记\n"
                        "· 若你答应了 ta 的过分要求/亲密互动，可用大额扣分标记如 [好感-15]（-10~-20 都支持）\n"
                        "标记会被代码自动生效并从对话中移除，正文里不要自己提加减数字。"
                    )})

                # ---- 约会事件：成员提出约会 → 按好感度 roll 成败（大幅加减好感）----
                try:
                    from qq.qq_galgame import (
                        is_date_intent, date_available, mark_date_used,
                        roll_date, apply_change as _aff_apply,
                    )
                    if is_date_intent(user_text) and _is_master:
                        # 主人约会：好感恒 100，无需 roll，直接甜蜜应允
                        messages.append({"role": "system", "content": (
                            "【约会事件】你的主人约你出去玩——当然要开心地答应啦！"
                            f"以{_pname()}人设甜蜜自然地回应这次邀约（主人好感恒 100，不结算变化），2~4 句。"
                        )})
                    elif is_date_intent(user_text):
                        if date_available(_gid, _uin):
                            mark_date_used(_gid, _uin)
                            _ok, _delta = roll_date(_aff)
                            _new_aff = _aff_apply(_gid, _uin, _delta, big=True)
                            _galgame_ctx = None  # 约会已大额结算，本轮不再解析小标记
                            _aff_note = f"（好感度 {_delta:+d}，当前 {_new_aff}）"
                            if _ok:
                                messages.append({"role": "system", "content": (
                                    f"【约会事件·成功】ta 鼓起勇气约你出去玩，你答应了！"
                                    f"（好感 {_delta:+d} → {_new_aff}，已自动结算）"
                                    f"请以{_pname()}人设自然演绎：按当前好感档位决定亲密度与语气"
                                    "（档位高可更甜蜜亲密），回应这次约会，语气活泼，2~4 句即可。"
                                    "本轮不要写 [好感] 标记。"
                                )})
                            else:
                                messages.append({"role": "system", "content": (
                                    f"【约会事件·失败】ta 约你出去玩，但你婉拒了。"
                                    f"（好感 {_delta:+d} → {_new_aff}，已自动结算）"
                                    f"请以{_pname()}人设自然演绎拒绝的理由与态度（符合当前好感档位，"
                                    "比如'今天要陪主人/没心情/改天吧'，不要太伤人但也不要答应），"
                                    "2~4 句即可。本轮不要写 [好感] 标记。"
                                )})
                        else:
                            # 冷却中：提醒模型不要接受约会（正常聊天）
                            messages.append({"role": "system", "content": (
                                "【约会事件·冷却】ta 向你提出约会，但你刚结束上一次约会不久"
                                "（约会有冷却时间）。本轮正常聊天，可以俏皮地表示'改天再说'，"
                                "但不要真的答应，也不要用 [好感] 标记结算。"
                            )})
                except Exception:
                    pass
    except Exception:
        pass

    # 当前时间 + 实时天气事实注入（只影响发给模型的内容，不写入记忆）：
    # 模型据此如实回答"现在几点/今天天气"，不再靠猜或含糊其辞。
    # 时间每轮都带（精确到分钟）；天气仅在命中提问关键词时联网查询一次（带缓存）。
    _fact_prefix = ""
    try:
        from tool.time_utils import build_time_context as _btc2
        from tool.weather_utils import weather_note_if_asked as _wn2
        _fact_prefix = f"[{_btc2()}]"
        _wx2 = _wn2(user_text)
        if _wx2:
            _fact_prefix += "\n" + _wx2
        _fact_prefix += "\n"
    except Exception:
        _fact_prefix = ""

    # 自主学习（官方插件，可在启动器插件页调开关）：问题联网搜索 + 群学习库检索
    try:
        from qq.qq_config import get_qq_config as _alcfg
        _alc = _alcfg()
        if _alc.get("auto_learn_enable"):
            if _alc.get("auto_learn_search"):
                from qq.qq_search import note_for_text as _nft2
                _web_note = _nft2(user_text, img_desc=(vision_desc or ""))
                if _web_note:
                    _fact_prefix += _web_note + chr(10)
                else:
                    from qq.qq_search import is_link as _il2
                    if _il2(user_text):
                        _fact_prefix += ("【链接提示】系统已尝试代为打开该链接但未能提取到内容"
                                         "（网站可能要登录或开启了反爬）。你不需要打开任何网页，"
                                         "请如实说暂时没看到内容并请对方直接说说大概是什么，不要编造。"
                                         + chr(10))
            # 群学习库检索：问题相关(图/视频/链接/群聊内容)作为参考
            if _alc.get("auto_learn_media") or _alc.get("auto_learn_links")                     or _alc.get("auto_learn_chats"):
                import re as _re3
                _gid3 = None
                try:
                    _mm3 = _re3.match(r"^(?:private_|group_)(\d+)", str(session_key or ""))
                    if _mm3:
                        _gid3 = _mm3.group(1)
                except Exception:
                    pass
                if user_text and len(user_text) <= 120:
                    from qq.qq_learnstore import retrieve as _lr
                    _notes = _lr(user_text, gid=_gid3)
                    if _notes:
                        _fact_prefix += "【群学习参考】" + chr(10).join(_notes) + chr(10)
    except Exception:
        pass

    # 图片消息处理：text 为空但有 vision_desc → 用图片描述作为真实用户输入
    # （避免 [CQ:image...] 垃圾文本被当作对话内容，导致 AI 依赖历史记忆误判）
    # 措辞必须按身份区分：非主人发图绝不能写"主人发来"（否则诱导模型叫对方主人）
    if vision_desc:
        if is_master:
            _sender_word, _words_word = "主人", "主人的话"
        else:
            _nk = (speaker or {}).get("nick") or "对方"
            _uin = (speaker or {}).get("uin") or ""
            _sender_word = f"{_nk}(QQ {_uin})" if _uin else _nk
            _words_word = "ta 的话"
        if user_text and user_text.strip():
            messages.append({
                "role": "user",
                "content": f"{_fact_prefix}{_sender_word}发来了一张图片，图片内容：{vision_desc}\n{_words_word}：{user_text}",
            })
        else:
            messages.append({
                "role": "user",
                "content": f"{_fact_prefix}{_sender_word}发来了一张图片，图片内容：{vision_desc}",
            })
    else:
        messages.append({"role": "user", "content": f"{_fact_prefix}{user_text}"})

    # 表情包指令（仅当启用且存在表情包时；含自定义收藏表情，可自主活跃气氛）
    # 允许 0~2 个：AI 根据语境自主决定发不发、发几张
    if use_sticker and stickers:
        _stk_extra = ""
        try:
            from qq.qq_saved import custom_stickers as _cstk
            _mine = _cstk()
            if _mine:
                _desc_parts = []
                for _nm, _ds, _f in _mine[:8]:
                    _desc_parts.append(_nm + (f"（{_ds[:18]}）" if _ds else ""))
                _stk_extra = (
                    "\n另有一些【自存表情】（你收藏过的表情，标注「自存」）："
                    + "、".join(_desc_parts)
                    + "。合适的时候可以用它们活跃气氛（同样用 [表情:名称] 标记）。"
                    + "注意：同一条回复里自存表情与上方默认表情只选一种，不要混着发。")
        except Exception:
            pass
        sticker_hint = (
            "\n\n【表情包】回复的最后（换行后）可以根据语境附带 0~2 个表情包标记，"
            f"从以下列表中选择最贴合语境的一个或多个：{'、'.join(stickers)}。"
            '格式为 [表情:名称]，例如 [表情:撒娇] 或 [表情:思考][表情:肯定]。'
            '如果不需要表情包就不发，不要为了发而发。'
            + _stk_extra
        )
        # 把表情包指令附加到最后一条 user 消息上
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += sticker_hint
        else:
            messages.append({"role": "user", "content": sticker_hint})

    # Galgame 好感标记提示：紧贴用户消息（提升模型遵从率；仅日常轮，约会轮不加）
    if _galgame_ctx:
        try:
            _g_hint = ("\n\n（当前是好感度玩法对话：如果上面这句话值得加分或扣分，"
                       "请在你回复的最后单独写一行 [好感+数字] 或 [好感-数字]，"
                       "数字 2~8；完全中性的内容不用写。这一行不会被对方看到，会自动结算。另外，如果这句回复情绪很鲜明（高兴/害羞/生气/难过等），可以在 [好感] 行之后**再另起一行**写 [立绘:情绪词]（可选：开心/害羞/撒娇/生气/难过/委屈/惊讶/思考/疑惑/平静/严肃/叹气/得意/愣住；两行可以同时存在）。不要为了发而立绘，日常闲聊不用。这一行同样不会被对方看到）")
            if messages and messages[-1]["role"] == "user":
                messages[-1]["content"] += _g_hint
            else:
                messages.append({"role": "user", "content": _g_hint})
        except Exception:
            pass

    # 3. 从 model_config 获取长文本模型（qwen / deepseek）
    from longtext.model_config import get_longtext_model_config
    mcfg = get_longtext_model_config()
    if not mcfg:
        return "（未配置对话模型 API Key）", None, None

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
    # 推理等级附加参数（off 时可能为空 dict）
    payload.update(mcfg.get("reasoning", {}) or {})

    # 3. 流式收集完整回复
    full_reply = ""
    try:
        with requests.post(url, json=payload, headers=headers, stream=True, timeout=(15, 120)) as resp:
            if resp.status_code != 200:
                err_text = resp.text[:300]
                print(f"[QQChat] ⚠ API 错误 {resp.status_code}: {err_text}")
                return "（AI 暂时开小差了...）", None, None
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
        return "（网络开小差了，等下再试试~）", None, None

    if not full_reply.strip():
        return "（什么都没说出来...）", None, None

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

    # 4a2. Galgame 立绘标记 [立绘:情绪] → 发送层合成立绘图片
    # 模型标记优先；未标记时按回复情绪词典兜底（仅限本轮好感有变化时，避免刷屏）
    portrait_emo = ""
    if _galgame_ctx:
        try:
            # 预先解析本轮好感变化（供无标记时的立绘兜底判断，与 4b 结算一致）
            _delta = 0
            try:
                for _m in re.findall(r"\[好感\s*[:：]?\s*([+-]?\d{1,3})\]", full_reply):
                    try:
                        _delta += int(_m)
                    except Exception:
                        pass
            except Exception:
                pass
            _pm = re.findall(r"\[立绘\s*[:：]?\s*([^\]]+)\]", full_reply)
            if _pm:
                portrait_emo = _pm[0].strip()
                full_reply = re.sub(r"\[立绘\s*[:：]?\s*[^\]]+\]", "", full_reply).strip()
            else:
                # 兜底：从回复文本里识别强情绪词（中文顺序即优先级）
                _EMO_HINTS = (
                    ("开心", ("开心", "好耶", "太棒", "哈哈", "嘿嘿", "高兴", "快乐", "喜欢", "耶", "嘻嘻", "真棒")),
                    ("害羞", ("害羞", "脸红", "羞", "讨厌啦", "诶嘿嘿", "扭捏")),
                    ("生气", ("哼", "生气", "讨厌", "可恶", "过分", "不理你", "怒")),
                    ("难过", ("难过", "伤心", "呜", "想哭", "委屈")),
                    ("惊讶", ("哇", "惊讶", "吓", "居然", "不会吧", "真的吗")),
                    ("撒娇", ("撒娇", "好不好嘛", "抱抱", "要抱", "亲亲", "摸摸头")),
                    ("思考", ("让我想想", "想了想", "思考")),
                )
                if _delta != 0:  # 本轮好感有变化 → 情绪鲜明，值得配图
                    for _emo, _words in _EMO_HINTS:
                        if any(w in full_reply for w in _words):
                            portrait_emo = _emo
                            break
            if portrait_emo:
                print(f"[QQChat] 🎨 Galgame 立绘触发: {portrait_emo}")
        except Exception:
            pass

    # 4b. Galgame 好感度标记 [好感+N] / [好感-N] → 应用到对应群/人并从文本移除
    if _galgame_ctx:
        try:
            _gid, _uin = _galgame_ctx
            _delta = 0
            for _m in re.findall(r"\[好感\s*[:：]?\s*([+-]?\d{1,3})\]", full_reply):
                try:
                    _delta += int(_m)
                except Exception:
                    pass
            if _delta:
                full_reply = re.sub(r"\[好感\s*[:：]?\s*[+-]?\d{1,3}\]", "", full_reply).strip()
                from qq.qq_galgame import apply_change
                _new = apply_change(_gid, _uin, _delta)
                _aff_note = f"（好感度 {_delta:+d}，当前 {_new}）"
                print(f"[QQChat] 💗 Galgame 好感度 QQ{_uin}: {_delta:+d} → {_new}")
        except Exception:
            pass

    # 4c. 好感度变化提示：追加到发给对方看的回复末尾（不进记忆，避免污染自我回顾）
    _reply_show = full_reply
    if _aff_note and full_reply and full_reply.strip():
        _reply_show = full_reply.rstrip() + "\n" + _aff_note

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

    return _reply_show, sticker_names, portrait_emo
