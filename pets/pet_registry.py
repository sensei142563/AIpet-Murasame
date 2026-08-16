# -*- coding: utf-8 -*-
"""
桌宠注册中心 — 多桌宠架构的核心入口。

职责：
1. 扫描 pets/ 目录下的所有桌宠角色包（含 pet.json）
2. 提供 pet_list.json 注册表（维护顺序/启用的桌宠）
3. 路径解析：把 pet.json 中的相对路径解析为绝对路径
4. 能力自动检测：根据实际文件是否存在覆盖 capabilities 字段
5. 全局默认值（如长文本默认音色 953244.wav）

设计：
- 引擎层只依赖本模块，不直接知道任何具体桌宠名
- pet.json 中的 capabilities 是"声明值"，此处做"实际检测"修正
"""
import os
import json

from tool.paths import app_base_dir

# ============ 目录基准 ============
# 必须用 app_base_dir()：exe 模式（PyInstaller onedir 壳）下 __file__ 位于 _internal/，
# 若用它推导会得到 _internal/pets（不存在）→ PCL 列表全空。
# app_base_dir() 在 exe 模式返回 exe 所在目录（绿色版根，pets/ 就在这里）。
BASE_DIR = app_base_dir()
PETS_DIR = os.path.join(BASE_DIR, "pets")
REGISTRY_JSON = os.path.join(PETS_DIR, "pet_list.json")

# ============ 全局默认值（无语音包时的兜底） ============
DEFAULT_LONG_AUDIO = os.path.join(BASE_DIR, "reference_voices", "long_chinese", "953244.wav")
DEFAULT_LONG_TEXT = "能和老师在一起，我真的，好高兴！"


def _load_json(path, default=None):
    try:
        # 先用 utf-8-sig（自动去除 BOM），失败则用纯 utf-8
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_pet_list() -> dict:
    """读取注册表（pet_list.json），不存在则自动扫描生成。

    返回清单 = 注册表条目（随仓库/绿色版分发）+ 本地 pets/ 里存在但未注册的
    角色包（仅内存合并，不写回注册表）：
    - 本地自用角色（未登记）在本机 PCL 正常显示、可用；
    - pet_list.json 始终保持「分发清单」，仓库/绿色版只含登记过的角色。
    每次加载时用各角色 pet.json 的最新 name/display_name/intro/avatar 刷新注册表条目。"""
    registry = _load_json(REGISTRY_JSON, None)
    if registry is None:
        registry = scan_pets()
        _save_json(REGISTRY_JSON, registry)
    else:
        _sync_registry_from_pet_json(registry)
        _merge_scanned_pets(registry)
    return registry


def _sync_registry_from_pet_json(registry: dict) -> bool:
    """用 pets/<id>/pet.json 的最新字段刷新注册表条目（name/display_name/intro/avatar），
    并把变更写回。只刷新已有条目，不登记磁盘上的新目录——新目录由 _merge_scanned_pets
    在内存中合并，保证 pet_list.json 始终只含「分发清单」。"""
    if not isinstance(registry, dict):
        return False
    changed = False
    for entry in registry.get("pets", []):
        pet_id = entry.get("id")
        if not pet_id:
            continue
        cfg = _load_json(os.path.join(PETS_DIR, pet_id, "pet.json"), None)
        if not cfg:
            continue
        fresh = {
            "name": cfg.get("name", pet_id),
            "display_name": cfg.get("display_name") or cfg.get("name", pet_id),
            "intro": cfg.get("intro", ""),
            "avatar": cfg.get("avatar", ""),
        }
        for key, val in fresh.items():
            if entry.get(key) != val:
                entry[key] = val
                changed = True

    if changed:
        _save_json(REGISTRY_JSON, registry)
    return changed


def _merge_scanned_pets(registry: dict) -> None:
    """把 pets/ 下存在 pet.json 但未注册的角色包合并进清单（仅内存，不写回）。

    这是「本地自用角色」的入口：本机可见、可用，但不进注册表，
    因此不会随仓库 / 绿色版分发。"""
    if not isinstance(registry, dict) or not os.path.isdir(PETS_DIR):
        return
    pets = registry.setdefault("pets", [])
    existing = {e.get("id") for e in pets}
    for entry in sorted(os.listdir(PETS_DIR)):
        if entry.startswith("_") or entry in existing:
            continue
        pet_dir = os.path.join(PETS_DIR, entry)
        if not os.path.isdir(pet_dir) or not os.path.exists(os.path.join(pet_dir, "pet.json")):
            continue
        cfg = _load_json(os.path.join(pet_dir, "pet.json"), None)
        if not cfg or not cfg.get("id"):
            continue
        pets.append({
            "id": entry,
            "name": cfg.get("name", entry),
            "display_name": cfg.get("display_name", cfg.get("name", entry)),
            "intro": cfg.get("intro", ""),
            "avatar": cfg.get("avatar", ""),
        })


def register_pet(pet_id: str) -> bool:
    """把 pets/<pet_id>/ 角色包注册进 pet_list.json（PCL「添加新桌宠」调用）。"""
    pet_dir = os.path.join(PETS_DIR, pet_id)
    cfg = _load_json(os.path.join(pet_dir, "pet.json"), None)
    if not os.path.isdir(pet_dir) or not cfg:
        return False
    registry = _load_json(REGISTRY_JSON, {"pets": [], "active": None})
    if not isinstance(registry, dict):
        registry = {"pets": [], "active": None}
    pets = registry.setdefault("pets", [])
    if any(e.get("id") == pet_id for e in pets):
        return True
    pets.append({
        "id": pet_id,
        "name": cfg.get("name", pet_id),
        "display_name": cfg.get("display_name", cfg.get("name", pet_id)),
        "intro": cfg.get("intro", ""),
        "avatar": cfg.get("avatar", ""),
    })
    _save_json(REGISTRY_JSON, registry)
    return True


def unregister_pet(pet_id: str) -> bool:
    """从 pet_list.json 移除桌宠条目（PCL「删除桌宠」调用）。"""
    registry = _load_json(REGISTRY_JSON, None)
    if not isinstance(registry, dict):
        return False
    pets = registry.get("pets", [])
    new_pets = [e for e in pets if e.get("id") != pet_id]
    if len(new_pets) == len(pets):
        return False
    registry["pets"] = new_pets
    _save_json(REGISTRY_JSON, registry)
    return True


def scan_pets() -> dict:
    """扫描 pets/ 目录，发现所有包含 pet.json 的桌宠包。"""
    pets = []
    if not os.path.isdir(PETS_DIR):
        return {"pets": [], "active": None}
    for entry in sorted(os.listdir(PETS_DIR)):
        # 跳过下划线开头的目录（如 _template 空白模板）
        if entry.startswith("_"):
            continue
        pet_dir = os.path.join(PETS_DIR, entry)
        pet_json_path = os.path.join(pet_dir, "pet.json")
        if not os.path.isdir(pet_dir) or not os.path.exists(pet_json_path):
            continue
        cfg = _load_json(pet_json_path, None)
        if not cfg or not cfg.get("id"):
            continue
        pets.append({
            "id": entry,
            "name": cfg.get("name", entry),
            "display_name": cfg.get("display_name", cfg.get("name", entry)),
            "intro": cfg.get("intro", ""),
            "avatar": cfg.get("avatar", ""),
        })
    return {"pets": pets, "active": pets[0]["id"] if pets else None}


def get_pet_ids() -> list:
    """返回所有已注册桌宠 ID 列表。"""
    registry = load_pet_list()
    return [p["id"] for p in registry.get("pets", [])]


def get_active_pet_id() -> str:
    """返回当前活动桌宠 ID（config.json 的 active_pet 或注册表 active）。"""
    cfg = _load_json(os.path.join(BASE_DIR, "config.json"), {})
    active = cfg.get("active_pet")
    if active:
        return active
    registry = load_pet_list()
    return registry.get("active") or (get_pet_ids()[0] if get_pet_ids() else "murasame")


def set_active_pet_id(pet_id: str) -> bool:
    """设置当前活动桌宠到 config.json（供 PCL / run_qq 使用）。"""
    if pet_id not in get_pet_ids():
        return False
    cfg = _load_json(os.path.join(BASE_DIR, "config.json"), {})
    cfg["active_pet"] = pet_id
    _save_json(os.path.join(BASE_DIR, "config.json"), cfg)
    return True


def get_pet_config(pet_id: str = None) -> dict:
    """返回指定桌宠（或当前活动）的完整 pet.json 配置。"""
    pet_id = pet_id or get_active_pet_id()
    pet_json = os.path.join(PETS_DIR, pet_id, "pet.json")
    cfg = _load_json(pet_json, None)
    if not cfg:
        return {}
    return cfg


def get_pet_dir(pet_id: str = None) -> str:
    """返回桌宠包目录的绝对路径。"""
    pet_id = pet_id or get_active_pet_id()
    return os.path.join(PETS_DIR, pet_id)


def resolve_path(rel_path: str, pet_id: str = None) -> str:
    """
    把 pet.json 中的相对路径解析为绝对路径。
    - 若路径存在于桌宠包内 → 返回桌宠包内路径
    - 若桌宠包内不存在但全局存在 → 返回全局路径（例如 reference_voices 等共享资源）
    - 否则直接拼 BASE_DIR 返回（可能不存在，由调用方处理）
    """
    if not rel_path:
        return ""
    pet_id = pet_id or get_active_pet_id()
    # 优先桌宠包内
    pet_path = os.path.join(PETS_DIR, pet_id, rel_path)
    if os.path.exists(pet_path):
        return pet_path
    # 其次全局
    global_path = os.path.join(BASE_DIR, rel_path)
    if os.path.exists(global_path):
        return global_path
    return pet_path  # 都不存在 → 返回桌宠包内路径（调用方自行处理缺失）


def get_prompt_path(kind: str = "short", pet_id: str = None) -> str:
    """获取人设 prompt 路径：short=短文本 / long=长文本(QQ也用)。"""
    cfg = get_pet_config(pet_id)
    pet_id = pet_id or get_active_pet_id()
    rel = cfg.get("prompt", {}).get(kind) or (f"{kind}_prompt.txt")
    return resolve_path(rel, pet_id)


def get_short_emotions(pet_id: str = None) -> list:
    """返回短文本可用情感列表（取自 pet.json voices.short_emotions）。"""
    cfg = get_pet_config(pet_id)
    return cfg.get("voices", {}).get("short_emotions", [])


def get_long_ref(pet_id: str = None) -> tuple:
    """
    返回 (参考音频路径, 参考文本)。
    桌宠有 voices.long_ref_audio → 用它；否则用全局默认 953244.wav。
    """
    cfg = get_pet_config(pet_id)
    pet_id = pet_id or get_active_pet_id()
    rel_audio = cfg.get("voices", {}).get("long_ref_audio", "")
    ref_text = cfg.get("voices", {}).get("long_ref_text", DEFAULT_LONG_TEXT)

    # 桌宠包内优先
    if rel_audio:
        pet_audio = os.path.join(PETS_DIR, pet_id, rel_audio)
        if os.path.exists(pet_audio):
            return pet_audio, ref_text
    # 全局兜底
    return DEFAULT_LONG_AUDIO, DEFAULT_LONG_TEXT


def get_short_voices_dir(pet_id: str = None) -> str:
    """返回短文本语音包目录（GPT-SoVITS 情感参考），不存在返回空串。"""
    cfg = get_pet_config(pet_id)
    pet_id = pet_id or get_active_pet_id()
    rel = cfg.get("voices", {}).get("short_ref_dir", "voices/short")
    path = os.path.join(get_pet_dir(pet_id), rel)
    return path if os.path.isdir(path) else ""


def get_short_emotion_dirs(pet_id: str = None) -> list:
    """返回短文本可用的情感目录名（含 asr.txt 的目录），用于情感分析。"""
    voices_dir = get_short_voices_dir(pet_id)
    if not voices_dir:
        return []
    return [
        d for d in os.listdir(voices_dir)
        if os.path.isdir(os.path.join(voices_dir, d))
        and os.path.exists(os.path.join(voices_dir, d, "asr.txt"))
    ]


def get_fgimages_dir(pet_id: str = None) -> str:
    """返回 2D 立绘图层目录（fgimages），不存在返回空串。"""
    pet_id = pet_id or get_active_pet_id()
    path = os.path.join(get_pet_dir(pet_id), "fgimages")
    return path if os.path.isdir(path) else ""


def get_live2d_dir(pet_id: str = None) -> str:
    """返回 Live2D 模型目录（含 DLL），不存在返回空串。"""
    cfg = get_pet_config(pet_id)
    pet_id = pet_id or get_active_pet_id()
    rel = cfg.get("model", {}).get("live2d_dir", "live2d")
    path = os.path.join(get_pet_dir(pet_id), rel)
    return path if os.path.isdir(path) else ""


def get_live2d_model_json(pet_id: str = None) -> str:
    """
    返回角色实际可用的 .model3.json 绝对路径，找不到返回空串。

    选择策略（防止选中残缺备份，例如某角色 live2d/ 目录下旧的备份
    model3.json 引用的 .moc3 已不存在）：
    1. pet.json 钉死的 model.live2d_model_json（相对角色包）
    2. live2d 目录顶层扫描所有 .model3.json
    3. 优先返回「引用的 .moc3 文件真实存在」的候选
    """
    pet_id = pet_id or get_active_pet_id()
    cfg = get_pet_config(pet_id)
    pet_dir = get_pet_dir(pet_id)

    candidates = []
    pinned = cfg.get("model", {}).get("live2d_model_json", "")
    if pinned:
        p = os.path.join(pet_dir, pinned)
        if os.path.exists(p):
            candidates.append(p)

    live2d_rel = cfg.get("model", {}).get("live2d_dir", "live2d")
    l2d_dir = os.path.join(pet_dir, live2d_rel)
    if os.path.isdir(l2d_dir):
        for f in sorted(os.listdir(l2d_dir)):
            if f.endswith(".model3.json"):
                p = os.path.join(l2d_dir, f)
                if p not in candidates:
                    candidates.append(p)

    if not candidates:
        return ""

    def _refs_exist(model_json_path: str) -> bool:
        """校验 model3.json 引用的 .moc3 是否真实存在（残缺备份返回 False）"""
        data = _load_json(model_json_path, None)
        if not isinstance(data, dict):
            return False
        refs = data.get("FileReferences", {})
        if not refs:
            return False
        base = os.path.dirname(model_json_path)
        moc = refs.get("Moc", "")
        if not moc or not os.path.exists(os.path.join(base, moc)):
            return False
        return True

    for c in candidates:
        if _refs_exist(c):
            return c
    # 都不完整 → 退回第一个候选（由调用方/加载方报错）
    return candidates[0]


def get_live2d_display(pet_id: str = None) -> dict:
    """
    返回角色 Live2D 显示/交互配置（阶段 E，含默认值兜底）：
    - window_ratio  : 窗口宽/高比（murasame 全身=0.67；方形半身模型≈1.0）
    - scale/offset  : 模型缩放与平移（修复头顶/鞋子被裁，参考 *.vtube.json 调校值）
    - font_scale    : 文字层字号缩放
    - head/talk 区间 : 摸头/对话交互区域（相对窗口高度的比例）
    """
    pet_id = pet_id or get_active_pet_id()
    cfg = get_pet_config(pet_id)
    m = cfg.get("model", {})
    inter = cfg.get("interaction", {}) or {}

    def _f(key, default):
        try:
            return float(m.get(key, default))
        except (TypeError, ValueError):
            return default

    def _fi(key, default):
        try:
            return float(inter.get(key, default))
        except (TypeError, ValueError):
            return default

    return {
        "window_ratio": _f("live2d_window_ratio", 0.67),
        "window_height_ratio": _f("live2d_window_height_ratio", 0.85),
        "scale": _f("live2d_scale", 1.0),
        "offset_x": _f("live2d_offset_x", 0.0),
        "offset_y": _f("live2d_offset_y", 0.0),
        "font_scale": _f("live2d_font_scale", 1.0),
        "head_top": _fi("head_top", 0.0),
        "head_bottom": _fi("head_bottom", 0.18),
        "talk_top": _fi("talk_top", 0.5),
        "talk_bottom": _fi("talk_bottom", 1.0),
        "edge_margin_x": _fi("edge_margin_x", 0.12),
        # 文本框位置微调（Shift+方向键调整后 F5 持久化）
        "text_offset_x": _fi("text_offset_x", 0.0),
        "text_offset_y": _fi("text_offset_y", 0.0),
        # 情绪→表情/动作映射（阶段 E）
        "emotions": cfg.get("model", {}).get("emotions", {}) or {},
        "motions": cfg.get("model", {}).get("motions", {}) or {},
        "default_expression": cfg.get("model", {}).get("default_expression", "") or "",
    }


def get_live2d_params(pet_id: str = None) -> dict:
    """从角色 *.vtube.json 的 ParameterSettings 提取参数输出范围（眨眼/口型上限），
    修复引擎里 0~1 硬编码（如 noir 眨眼上限 1.9、口型上限 2.1）。"""
    pet_id = pet_id or get_active_pet_id()
    cfg = get_pet_config(pet_id)
    pet_dir = get_pet_dir(pet_id)
    live2d_rel = cfg.get("model", {}).get("live2d_dir", "live2d")
    l2d_dir = os.path.join(pet_dir, live2d_rel)
    result = {"eye_open_max": 1.0, "mouth_open_max": 1.0}
    if not os.path.isdir(l2d_dir):
        return result
    for vf in os.listdir(l2d_dir):
        if not vf.endswith(".vtube.json"):
            continue
        data = _load_json(os.path.join(l2d_dir, vf), None)
        if not isinstance(data, dict):
            continue
        for ps in data.get("ParameterSettings", []):
            out = ps.get("OutputLive2D", "")
            try:
                upper = float(ps.get("OutputRangeUpper", 1.0))
            except (TypeError, ValueError):
                continue
            if out == "ParamEyeLOpen":
                result["eye_open_max"] = max(1.0, upper)
            elif out == "ParamMouthOpenY":
                result["mouth_open_max"] = max(1.0, upper)
    return result


def save_live2d_display(pet_id: str = None, **values) -> bool:
    """把显示参数写回角色 pet.json 的 model/ 块（Live2D 调参热键 F5 持久化）。"""
    pet_id = pet_id or get_active_pet_id()
    pet_json = os.path.join(PETS_DIR, pet_id, "pet.json")
    cfg = _load_json(pet_json, None)
    if not isinstance(cfg, dict):
        return False
    model = cfg.setdefault("model", {})
    key_map = {
        "window_ratio": "live2d_window_ratio",
        "window_height_ratio": "live2d_window_height_ratio",
        "scale": "live2d_scale",
        "offset_x": "live2d_offset_x",
        "offset_y": "live2d_offset_y",
        "font_scale": "live2d_font_scale",
    }
    inter_key_map = {"text_offset_x": "text_offset_x", "text_offset_y": "text_offset_y"}
    for k, v in values.items():
        if k in key_map:
            model[key_map[k]] = v
        elif k in inter_key_map:
            cfg.setdefault("interaction", {})[k] = v
    _save_json(pet_json, cfg)
    print(f"[pet_registry] 已保存显示参数到 {pet_id}/pet.json: {values}")
    return True


def get_portrait_prompts(pet_id: str = None) -> dict:
    """
    返回角色的立绘图层映射（portrait_prompts.json）。
    结构：{"prompt_template": str, "sets": {"a": {...}, "b": {...}}}
    文件不存在 → 返回空 dict（调用方回退默认）。
    """
    pet_id = pet_id or get_active_pet_id()
    path = os.path.join(PETS_DIR, pet_id, "portrait_prompts.json")
    data = _load_json(path, None)
    return data if isinstance(data, dict) else {}


def get_sticker_dir(pet_id: str = None) -> str:
    """返回 QQ 表情包目录（不存在则返回空字符串，QQ 不发图）。"""
    cfg = get_pet_config(pet_id)
    pet_id = pet_id or get_active_pet_id()
    rel = cfg.get("sticker", {}).get("dir", "")
    if not rel:
        return ""
    path = os.path.join(PETS_DIR, pet_id, rel)
    return path if os.path.isdir(path) else ""


def get_memory_dir(pet_id: str = None) -> str:
    """返回角色记忆目录（隔离时各角色独立）。"""
    cfg = get_pet_config(pet_id)
    pet_id = pet_id or get_active_pet_id()
    rel = cfg.get("memory", {}).get("dir", "memory")
    return os.path.join(PETS_DIR, pet_id, rel)


def detect_capabilities(pet_id: str = None) -> dict:
    """
    根据实际文件检测能力（覆盖 pet.json 的声明）：
    - chat           : 有短或长人设 prompt
    - short_tts      : voices/short/ 至少有 1 个情感目录含音频
    - long_tts       : voices/long/ 有 wav 或全局默认存在
    - has_live2d     : live2d_dir 下有 .model3.json
    - has_fgimages   : 有图层文件（fgimages/）
    - screen/camera/face/qq : 引擎能力（默认 true）
    """
    pet_id = pet_id or get_active_pet_id()
    cfg = get_pet_config(pet_id)
    pet_dir = get_pet_dir(pet_id)
    caps = dict(cfg.get("capabilities", {}))

    # chat
    short_p = cfg.get("prompt", {}).get("short")
    long_p = cfg.get("prompt", {}).get("long")
    caps["chat"] = bool(
        (short_p and os.path.exists(os.path.join(pet_dir, short_p)))
        or (long_p and os.path.exists(os.path.join(pet_dir, long_p)))
    )

    # short_tts
    short_dir = os.path.join(pet_dir, cfg.get("voices", {}).get("short_ref_dir", "voices/short"))
    has_short = False
    if os.path.isdir(short_dir):
        for emo in os.listdir(short_dir):
            emo_dir = os.path.join(short_dir, emo)
            if os.path.isdir(emo_dir) and any(
                f.lower().endswith((".wav", ".mp3", ".flac"))
                for f in os.listdir(emo_dir)
            ):
                has_short = True
                break
    caps["short_tts"] = has_short

    # long_tts: 角色自带 或 全局默认 953244.wav 存在
    long_rel = cfg.get("voices", {}).get("long_ref_audio", "")
    if long_rel and os.path.exists(os.path.join(pet_dir, long_rel)):
        caps["long_tts"] = True
    else:
        caps["long_tts"] = os.path.exists(DEFAULT_LONG_AUDIO)

    # has_live2d
    live2d_rel = cfg.get("model", {}).get("live2d_dir", "")
    has_l2d = False
    if live2d_rel:
        l2d_path = os.path.join(pet_dir, live2d_rel)
        if os.path.isdir(l2d_path):
            has_l2d = any(f.endswith(".model3.json") for f in os.listdir(l2d_path))
    caps["has_live2d"] = has_l2d

    # has_fgimages
    fg_dir = os.path.join(pet_dir, "fgimages")
    caps["has_fgimages"] = os.path.isdir(fg_dir) and len(os.listdir(fg_dir)) > 0

    return caps


def get_all_pets_summary() -> list:
    """返回所有桌宠的摘要信息（PCL 桌宠列表用）。"""
    registry = load_pet_list()
    result = []
    for p in registry.get("pets", []):
        pet_id = p["id"]
        cfg = get_pet_config(pet_id)
        caps = detect_capabilities(pet_id)
        result.append({
            "id": pet_id,
            "name": p["name"],
            "display_name": p["display_name"],
            "intro": p["intro"],
            "avatar": p["avatar"],
            "model_default": cfg.get("model", {}).get("default", "2d"),
            "capabilities": caps,
            "is_active": (pet_id == get_active_pet_id()),
        })
    return result


if __name__ == "__main__":
    # 自测
    print("=== 桌宠注册中心自测 ===")
    print("注册表:", load_pet_list())
    print("桌宠列表:", get_pet_ids())
    print("当前活动:", get_active_pet_id())
    if get_pet_ids():
        pid = get_pet_ids()[0]
        print(f"\n[{pid}] 配置:", get_pet_config(pid))
        print(f"[{pid}] 能力检测:", detect_capabilities(pid))
        print(f"[{pid}] 长文本参考:", get_long_ref(pid))
        print(f"[{pid}] 记忆目录:", get_memory_dir(pid))
