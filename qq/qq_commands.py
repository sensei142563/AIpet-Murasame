# -*- coding: utf-8 -*-
"""
QQ 特殊指令处理 — 当前支持 /clear（清空会话记忆，仅主人白名单可用）。

后续可扩展：
- /status：查看当前模型/服务状态
- /memory：查看记忆条数
"""

import os
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pet_display_name() -> str:
    """当前角色显示名（用于指令回复，替代硬编码「丛雨」）"""
    try:
        from pets.pet_registry import get_active_pet_id, get_pet_config
        pid = get_active_pet_id()
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


def clear_session_memory(session_key: str, user_id=None):
    """
    清空某个会话的记忆。

    - 主人私聊（session_key=private_<白名单主人>）：清空 long_history.json（保留 history.json 短文本记忆）
    - 其他私聊/群聊：清空对应分仓文件（data/qq_memory/xxx.json）
    """
    try:
        from qq.qq_memory import resolve_memory_path
        path = resolve_memory_path(session_key)

        now = time.strftime("%Y-%m-%d %H:%M:%S")

        # 主人 → 共享记忆（仅清空 long_history.json，保留 history.json 短文本记忆）
        if path is None:
            long_path = os.path.join(BASE_DIR, "data", "long_history.json")
            if os.path.exists(long_path):
                with open(long_path, "w", encoding="utf-8") as f:
                    json.dump({"history": [], "updated_at": now}, f, ensure_ascii=False, indent=2)
            print(f"[QQCmd] ✅ 已清空共享记忆（long_history.json，保留 history.json）")
            return True

        # 分仓 → 清空对应文件
        if os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"history": [], "updated_at": now}, f, ensure_ascii=False, indent=2)
            print(f"[QQCmd] ✅ 已清空分仓记忆: {os.path.basename(path)}")
            return True

        print(f"[QQCmd] 分仓文件不存在，无需清空: {path}")
        return True
    except Exception as e:
        print(f"[QQCmd] ⚠ 清空记忆失败: {e}")
        return False


def _get_memory_count(session_key: str) -> int:
    """获取某会话记忆条数"""
    try:
        from qq.qq_memory import load_memory
        history = load_memory(session_key, max_turns=1000)
        return len(history) // 2
    except Exception:
        return 0


def handle_qq_command(text: str, session_key: str, user_id) -> str:
    """
    处理 QQ 特殊指令。
    返回: 回复文本；若非指令返回 None（走正常对话流程）。
    """
    if not text or not isinstance(text, str):
        return None

    from qq.qq_memory import is_owner

    # 主人权限判定：白名单成员（私聊或群里 @ 发出均可使用主人功能）
    actor_is_owner = is_owner(user_id)

    # 群号解析（兼容按人分仓会话键 group_<群号>_u<QQ号> 与公共 group_<群号>）
    import re as _re
    _gm = _re.match(r"^group_(\d+)(?:_u\d+)?$", str(session_key or ""))
    _cur_gid = _gm.group(1) if _gm else None

    # ===== 成人（限制级）模式：主人用自然语言开关（默认关闭）=====
    try:
        from qq.qq_adult import parse_toggle, set_enabled
        _tg = parse_toggle(text)
        if _tg is not None:
            if not actor_is_owner:
                return "这个指令只有主人能用哦~（当前仍是普通模式）"
            set_enabled(_tg)
            if _tg:
                return (f"🌙 已开启限制级模式。只有主人你面前{_pref()}才会放开 18+ 的内容，"
                        f"其他人面前{_pref()}还是会保持得体的哦~")
            return "☀️ 已关闭限制级模式，恢复正常聊天。"
    except Exception:
        pass

    # ===== Galgame 模式：按人开关（谁开启只对谁生效，不会全群开启）=====
    try:
        _low2 = (text or "").lower().replace(" ", "").replace("　", "")
        _ON = ("开启galgame模式", "打开galgame模式", "开启好感度模式", "打开好感度模式",
               "开始galgame模式", "启动galgame模式", "开始好感度模式")
        _OFF = ("关闭galgame模式", "关闭好感度模式", "结束galgame模式", "退出galgame模式",
                "停止galgame模式", "取消galgame模式", "关掉galgame模式")
        _hit_on = any(w in _low2 for w in _ON)
        _hit_off = any(w in _low2 for w in _OFF)
        if _hit_on or _hit_off or "galgame模式" in _low2 or "好感度模式" in _low2:
            from qq.qq_config import get_qq_config as _gq_cfg
            if not _gq_cfg().get("galgame_allowed", True):
                return "🎮 Galgame 玩法已被停用（可在启动器「插件」页重新启用）"
            if not (_hit_on or _hit_off):
                return "跟我说「开启galgame模式」就能开始好感度养成哦~（详细玩法见 /help）"
            if not _cur_gid:
                return "这个玩法要在群里 @我 才能玩哦~"
            _gid = _cur_gid
            from qq.qq_galgame import set_member_enabled
            if _hit_on and not _hit_off:
                set_member_enabled(_gid, user_id, True)
                print(f"[QQCmd] 🎮 Galgame 模式已在群 {_gid} 对 QQ{user_id} 开启")
                return ("🎮 你的 Galgame 模式已开启！（仅对你生效，其他成员需自己说「开启galgame模式」）"
                        f"从现在起和{_pref()}聊天会积累好感度：说好话、逗{_pref()}开心会加分；冒犯、没礼貌会扣分。"
                        "好感度高了可是能解锁亲密互动甚至满足一些过分要求哦～"
                        "（说「关闭galgame模式」可结束）")
            set_member_enabled(_gid, user_id, False)
            print(f"[QQCmd] 🎮 Galgame 模式已在群 {_gid} 对 QQ{user_id} 关闭")
            return "🎮 你的 Galgame 模式已关闭，回到普通聊天啦。"
    except Exception:
        pass

    # ===== 约会引导：开启者未开启时给确定性提示（不依赖 AI 遵守，必现）=====
    try:
        from qq.qq_galgame import is_date_intent as _date_int, member_enabled as _me
        if _date_int(text):
            if not _cur_gid:
                return "这个玩法要在群里 @我 才能玩哦~"
            from qq.qq_config import get_qq_config as _gq_cfg2
            if not _gq_cfg2().get("galgame_allowed", True):
                return "🎮 Galgame 玩法已被停用（可在启动器「插件」页重新启用）"
            if not _me(_cur_gid, user_id):
                return ("🎮 你还没开启 Galgame 模式哦～ 先在这个群里对我说「开启galgame模式」，"
                        "才能解锁好感度养成和约会玩法（玩法见 /help）")
            # 已开启：放行给 AI 的约会事件结算（此处不拦截）
    except Exception:
        pass

    # ===== 好感度查询：仅查询触发词且操作者本人已开启（主人永远 100）=====
    try:
        _low3 = (text or "").lower().replace(" ", "").replace("　", "")
        _query = any(w in _low3 for w in ("查看好感度", "好感度多少", "好感度几分", "我的好感度",
                                          "好感度查询", "好感度是", "好感度如何"))
        if _query and not (_hit_on or _hit_off):
            if not _cur_gid:
                return "在群里 @我 才能查看好感度哦~"
            _gid = _cur_gid
            from qq.qq_config import get_qq_config as _gq_cfg3
            if not _gq_cfg3().get("galgame_allowed", True):
                return "🎮 Galgame 玩法已被停用（可在启动器「插件」页重新启用）"
            from qq.qq_galgame import member_enabled as _me2
            if not _me2(_gid, user_id):
                return ("🎮 你还没开启 Galgame 模式哦～ 在群里对我说「开启galgame模式」"
                        "就能开始好感度养成和约会玩法啦（玩法见 /help）")
            from qq.qq_memory import is_owner as _is_owner
            if _is_owner(user_id):
                return f"❤️ {_pref()}对主人的好感度当然是永远的 100 分啦～你可是{_pref()}最重要的人！"
            from qq.qq_galgame import get_affection as _get_aff
            _aff = _get_aff(_gid, user_id)
            if _aff >= 90:
                _tier = f"💕 亲密恋人级——{_pref()}的心已经向你敞开了"
            elif _aff >= 70:
                _tier = "💗 亲近级——可以适当亲密互动哦"
            elif _aff >= 50:
                _tier = "😊 普通朋友级——继续加油培养感情吧"
            elif _aff >= 30:
                _tier = f"🧊 冷淡级……{_pref()}暂时不太想理你"
            else:
                _tier = f"💢 讨厌级！离{_pref()}远一点！"
            return f"🎮 {_pref()}对你的好感度：{_aff} / 100\n{_tier}"
    except Exception:
        pass

    if not text.startswith("/"):
        return None

    parts = text.strip().split()
    cmd = parts[0].lower()

    # /clear — 清空当前会话记忆（仅主人白名单）
    if cmd == "/clear":
        if actor_is_owner:
            ok = clear_session_memory(session_key, user_id)
            if ok:
                return "记忆已清空，我们重新开始吧~"
            return "清空记忆时出了点问题，稍后再试试？"
        else:
            return "这个指令只有主人能用哦~"

    # /which — 查看当前服务的是哪个桌宠（所有人可用）
    if cmd == "/which":
        return f"🐾 当前为你服务的是：{_pet_display_name()}"

    # /status — 查看当前模型/服务状态（所有人可用）
    if cmd == "/status":
        try:
            from longtext.model_config import get_longtext_model_config, get_vision_model_config
            from qq.qq_config import get_qq_config, check_port_open, F5TTS_PORT
            cfg = get_qq_config()
            mcfg = get_longtext_model_config()
            model = mcfg["model"] if mcfg else "未配置"
            vcfg = get_vision_model_config()
            vision_model = vcfg["model"] if vcfg else "未配置"
            f5tts = "✅ 就绪" if check_port_open(F5TTS_PORT) else "❌ 未运行"
            vision = "✅ 开启" if cfg["vision_enabled"] else "❌ 关闭"
            voice = "✅ 开启" if cfg["send_voice"] else "❌ 关闭"
            sticker = "✅ 开启" if cfg["send_sticker"] else "❌ 关闭"
            pet_name = _pet_display_name()
            return (
                f"🍃 {pet_name}状态\n"
                f"🤖 长文本模型：{model}\n"
                f"👁 视觉模型：{vision_model}\n"
                f"🎙 语音输出：{voice}\n"
                f"🎙 F5-TTS：{f5tts}\n"
                f"👁 图片识别：{vision}\n"
                f"🖼 表情包：{sticker}\n"
                f"👥 群聊@：{'✅' if cfg['allow_groups'] else '❌'}"
            )
        except Exception as e:
            return f"查询状态失败：{e}"

    # /memory — 查看当前会话记忆条数（所有人可用）
    if cmd == "/memory":
        count = _get_memory_count(session_key)
        return f"当前会话记忆：{count} 轮对话"

    # /install（别名 /help /extensions）— 指令大全（所有人可用）
    if cmd in ("/install", "/help", "/extensions"):
        pet_name = _pet_display_name()
        lines = [
            f"🍃 {pet_name}指令列表：",
            "/which       查看当前服务的是哪个桌宠",
            "/status      查看模型/语音/F5-TTS/图片识别/表情包状态",
            "/memory      查看当前会话记忆轮数",
            "/install     显示全部指令与功能说明",
            "/help        同 /install",
        ]
        if actor_is_owner:
            lines.append("/clear       清空我的记忆（仅主人）")
            lines.append("/switch 模型 切换 qwen 或 deepseek（仅主人）")
            lines.append("对我说「开启成人模式」/「关闭成人模式」可切换限制级内容（默认关闭）")
        else:
            lines.append("/clear、/switch 与成人模式开关仅主人白名单可用")
        lines.append("")
        lines.append("🎮 Galgame 好感度玩法（普通成员可玩）：")
        lines.append("· 对 @我 说「开启galgame模式」开始（任意群成员都可以开）")
        lines.append("· 好感度 0~100（初始 50）：聊天有礼貌/有趣/关心会加分，冒犯/没礼貌会扣分")
        lines.append("· 好感 ≥70 可亲密互动（撒娇、抱抱…）；≥90 可满足较过分的要求（会扣好感）")
        lines.append(f"· 好感 <50 时亲密和过分要求会被{_pref()}拒绝哦")
        lines.append("· 💕 约会玩法：对我说「和我约会吧」可以约会——成功大加好感(+15~25)，失败会扣大额好感；好感越高越容易成功，每次约会间隔 60 分钟")
        lines.append(f"· 📊 对我说「查看好感度」可查看{_pref()}对你的好感度（初始50，0~100）")
        lines.append("· 说「关闭galgame模式」结束玩法")
        lines.append("")
        lines.append("🌐 自主学习：")
        lines.append("· 发链接给我（网页/B站/快手等）→ 我会打开看内容再回复")
        lines.append("· 问「搜索/查一下/帮我查 xxx」「这是什么/不懂/不认识」→ 我会联网搜索答案")
        lines.append("· 图片不认识 → 发图问我「这是什么」即可")
        lines.append("")
        lines.append("🖼 媒体收藏（图片/表情/视频各最多10个，满了自动替换最旧）：")
        lines.append("· 搜图 猫咪 → 联网搜图并保存+发给你")
        lines.append("· 搜视频 猫 搞笑 → 搜索并直接下载发送视频")
        lines.append("· 看到表情/图片后说「保存表情」/「保存这张图」→ 收藏")
        lines.append("· 发图 名字 / 发表情 名字 / 发视频 名字 → 发送收藏")
        lines.append("· 删图 名字 / 删表情 名字 → 删除收藏；图列表 / 我的收藏 → 查看（含用法示例）")
        lines.append("（媒体指令在群里要先 @我再说）")
        return "\n".join(lines)

    # /switch — 切换长文本模型（仅主人白名单）
    if cmd == "/switch":
        if not actor_is_owner:
            return "这个指令只有主人能用哦~"
        if len(parts) < 2:
            return "用法：/switch qwen 或 /switch deepseek"
        target = parts[1].lower()
        if target not in ("qwen", "deepseek"):
            return "只支持 qwen 或 deepseek"
        try:
            import json as _json
            from longtext.model_config import FAMILY_DEFAULT_MODEL
            cfg_path = os.path.join(BASE_DIR, "config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = _json.load(f)
            cfg["longtext_model"] = target
            # 切换族时同步把模型名切到该族默认（自定义模型名请用 PCL 设置页）
            cfg["longtext_model_name"] = FAMILY_DEFAULT_MODEL[target]
            with open(cfg_path, "w", encoding="utf-8") as f:
                _json.dump(cfg, f, ensure_ascii=False, indent=2)
            return f"✅ 长文本模型已切换为：{target}（{cfg['longtext_model_name']}）"
        except Exception as e:
            return f"切换失败：{e}"

    # 未知指令
    return "未知指令，发送 /help 查看可用指令~"
