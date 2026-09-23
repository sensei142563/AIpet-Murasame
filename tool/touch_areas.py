# -*- coding: utf-8 -*-
"""触摸互动区域（摸头 / 胸口 / 小腹 / 下体 / 大腿 / 小腿 / 脚 / 胳膊 / 手掌）。

坐标约定：**归一化矩形 [x, y, w, h]，取值 0~1**，相对「桌宠窗口 / 立绘显示区」的
宽高。桌宠窗口是按立绘尺寸 1:1 显示的（setPixmap 后 resize 到图片大小），
Live2D 也一样（模型画布 = 控件尺寸），所以这个坐标系在两种模式下都成立，
编辑器里看到的框位置 = 桌宠身上真正生效的位置。

数据存在角色包 pet.json：
    "touch": { "enabled": true, "areas": { "head": [x,y,w,h], ... } }
"""

import json
import os

# ── 区域定义：(键, 显示名, 默认矩形, 抚摸语气, 轻点语气) ──
# 默认矩形按「常见半身立绘」给了一套能用的值，用户可在编辑器里自由拖动/缩放。
AREAS = [
    ("head",      "头（摸头）",       [0.30, 0.01, 0.40, 0.15],
     "主人摸了摸你的头",             "主人轻轻戳了戳你的头"),
    ("chest",     "胸部（胸口）",     [0.33, 0.20, 0.34, 0.09],
     "主人把手按在你的胸口上揉了揉",  "主人轻轻戳了戳你的胸口"),
    ("belly",     "小腹",             [0.34, 0.30, 0.32, 0.08],
     "主人摸了摸你的小腹",           "主人轻轻戳了戳你的小腹"),
    ("privates",  "下体（隐私部位）",  [0.37, 0.39, 0.26, 0.07],
     "主人的手碰到了你的私密部位",    "主人隔着衣服轻轻碰了一下你的私密部位"),
    # ── 四肢各两个框（左 / 右）──
    ("thigh_l",   "左大腿",           [0.34, 0.47, 0.15, 0.11],
     "主人摸了摸你的左大腿",         "主人戳了戳你的左大腿"),
    ("thigh_r",   "右大腿",           [0.51, 0.47, 0.15, 0.11],
     "主人摸了摸你的右大腿",         "主人戳了戳你的右大腿"),
    ("shin_l",    "左小腿",           [0.35, 0.60, 0.14, 0.12],
     "主人摸了摸你的左小腿",         "主人戳了戳你的左小腿"),
    ("shin_r",    "右小腿",           [0.51, 0.60, 0.14, 0.12],
     "主人摸了摸你的右小腿",         "主人戳了戳你的右小腿"),
    ("foot_l",    "左脚（足部）",     [0.35, 0.74, 0.14, 0.10],
     "主人捏了捏你的左脚",           "主人戳了戳你的左脚"),
    ("foot_r",    "右脚（足部）",     [0.51, 0.74, 0.14, 0.10],
     "主人捏了捏你的右脚",           "主人戳了戳你的右脚"),
    ("arm_l",     "左胳膊",           [0.12, 0.22, 0.15, 0.28],
     "主人摸了摸你的左胳膊",         "主人戳了戳你的左胳膊"),
    ("arm_r",     "右胳膊",           [0.73, 0.22, 0.15, 0.28],
     "主人摸了摸你的右胳膊",         "主人戳了戳你的右胳膊"),
    ("hand_l",    "左手掌",           [0.12, 0.52, 0.15, 0.12],
     "主人握住了你的左手",           "主人碰了碰你的左手"),
    ("hand_r",    "右手掌",           [0.73, 0.52, 0.15, 0.12],
     "主人握住了你的右手",           "主人碰了碰你的右手"),
]

# 老配置里的「单框」键 → 现在拆成左右两个（迁移用）
LEGACY_SPLIT = {
    "thigh": ("thigh_l", "thigh_r"), "shin": ("shin_l", "shin_r"),
    "foot": ("foot_l", "foot_r"), "arm": ("arm_l", "arm_r"),
    "hand": ("hand_l", "hand_r"),
}

AREA_KEYS = [k for k, _n, _d, _a, _b in AREAS]
LABELS = {k: n for k, n, _d, _a, _b in AREAS}
DEFAULTS = {k: list(d) for k, _n, d, _a, _b in AREAS}
_REACT = {k: (a, b) for k, _n, _d, a, b in AREAS}


# 自定义部位（角色自己加的，比如尾巴/耳朵/角）——名字存 pet.json 的 touch.labels
_GENERIC_STROKE = "主人摸了摸你的{label}"
_GENERIC_TAP = "主人戳了戳你的{label}"


def labels(pet_id: str = None) -> dict:
    """部位显示名（默认 14 个 + 该角色自己加的自定义部位）"""
    out = dict(LABELS)
    try:
        from pets.pet_registry import get_pet_config
        cfg = get_pet_config(pet_id) or {}
        custom = ((cfg.get("touch") or {}).get("labels") or {})
        for k, v in (custom or {}).items():
            out[str(k)] = str(v)
    except Exception:
        pass
    return out


def custom_keys(pet_id: str = None):
    """该角色自定义部位的键（不在默认表里的）"""
    try:
        areas = get_pet_areas(pet_id)
        return [k for k in areas if k not in LABELS]
    except Exception:
        return []


def make_key(label: str, existing=None) -> str:
    """用名字生成唯一键（英文/拼音都不要求，直接用 custom_序号）"""
    existing = set(existing or [])
    i = 1
    while f"custom_{i}" in existing:
        i += 1
    return f"custom_{i}"


def defaults():
    return {k: list(v) for k, v in DEFAULTS.items()}


# 触摸的「即时反应」短句：不等云端返回，先让对话框立刻有反应
# （正式台词随后由模型给出并覆盖它，这样网络慢/失败时也不会像"没反应"）
_QUICK = {
    "head": "唔……好舒服～",
    "chest": "呀…！别、别突然摸那里…",
    "belly": "呜…好痒…",
    "privates": "呜…！那、那里不行！",
    "thigh_l": "呀…！", "thigh_r": "呀…！",
    "shin_l": "唔…", "shin_r": "唔…",
    "foot_l": "呀…别捏脚啦！", "foot_r": "呀…别捏脚啦！",
    "arm_l": "嗯…？", "arm_r": "嗯…？",
    "hand_l": "唔…牵手吗…", "hand_r": "唔…牵手吗…",
}


def reaction(key: str, gesture: str = "stroke", pet_id: str = None) -> str:
    """区域 + 手势 → 送去给模型的一句"发生的事情"。

    gesture: "stroke" 抚摸（按住拖动）/ "tap" 轻点（按下就松开）
    """
    pair = _REACT.get(str(key))
    if not pair:
        # 自定义部位：用通用文案 + 部位名（名字从角色配置里取）
        try:
            nm = labels(pet_id).get(str(key)) or "身体"
        except Exception:
            nm = "身体"
        tpl = _GENERIC_STROKE if str(gesture) == "stroke" else _GENERIC_TAP
        return tpl.format(label=nm)
    return pair[0] if str(gesture) == "stroke" else pair[1]


def _clamp01(v, fallback=0.0):
    try:
        f = float(v)
    except Exception:
        return float(fallback)
    return max(0.0, min(1.0, f))


def norm_rect(rect, fallback=None):
    """把任意输入整成合法的归一化矩形 [x,y,w,h]（宽高至少 0.01）"""
    fb = fallback or [0.3, 0.3, 0.2, 0.1]
    try:
        x, y, w, h = [float(v) for v in list(rect)[:4]]
    except Exception:
        x, y, w, h = [float(v) for v in fb]
    x, y = _clamp01(x, fb[0]), _clamp01(y, fb[1])
    w = max(0.01, min(1.0 - x, _clamp01(w, fb[2]) if w else fb[2]))
    h = max(0.01, min(1.0 - y, _clamp01(h, fb[3]) if h else fb[3]))
    return [round(x, 4), round(y, 4), round(w, 4), round(h, 4)]


def hit_area(areas: dict, nx: float, ny: float, off=()) -> str:
    """归一化坐标命中哪个区域（多个重叠时取面积最小的那个，便于精细区域优先）。

    off：要跳过的部位键（被禁用的部位不响应触摸）。
    """
    _off = set(str(k) for k in (off or ()))
    hit = []
    for k, r in (areas or {}).items():
        if str(k) in _off:
            continue
        try:
            x, y, w, h = [float(v) for v in r[:4]]
        except Exception:
            continue
        if x <= nx <= x + w and y <= ny <= y + h:
            hit.append((w * h, k))
    if not hit:
        return ""
    hit.sort()
    return hit[0][1]


# ══════════════ pet.json 读写 ══════════════
# 2D 与 Live2D 的触摸区域**各自独立**（类比对话框：text_box_2d / text_box_live2d）：
#   touch.areas_2d / touch.areas_live2d  → 两套互不影响的范围
#   touch.disabled_2d / disabled_live2d  → 各自禁用的部位（默认部位不能删，但可禁用）
#   touch.labels                          → 自定义部位名字（两套共用）
#   touch.areas                           → 旧版单套配置（会作为两套的初始值，向后兼容）
def _mode_key(mode: str) -> str:
    m = str(mode or "").lower()
    return "areas_live2d" if m.startswith("live") else "areas_2d"


def _disabled_key(mode: str) -> str:
    m = str(mode or "").lower()
    return "disabled_live2d" if m.startswith("live") else "disabled_2d"


def get_disabled(pet_id: str = None, mode: str = "2d") -> list:
    """该模式下被禁用的部位（这些部位不响应触摸）"""
    try:
        from pets.pet_registry import get_pet_config
        cfg = get_pet_config(pet_id) or {}
        t = cfg.get("touch") or {}
        v = t.get(_disabled_key(mode)) or []
        return [str(x) for x in v if isinstance(x, (str, int))]
    except Exception:
        return []


def get_pet_areas(pet_id: str = None, mode: str = "2d") -> dict:
    """取该角色的触摸区域（缺省项用默认值补齐；老角色也能直接用）"""
    areas = defaults()
    try:
        from pets.pet_registry import get_pet_config
        cfg = get_pet_config(pet_id) or {}
        _t = (cfg.get("touch") or {})
        saved = (_t.get(_mode_key(mode)) or _t.get("areas") or {})
        # 旧配置只有「大腿/小腿/脚/胳膊/手掌」一个框 → 拆成左右两个（右侧镜像）
        for old_k, (lk, rk) in LEGACY_SPLIT.items():
            if old_k in saved and lk not in saved:
                try:
                    x, y, w, h = [float(t) for t in saved[old_k][:4]]
                    saved = dict(saved)
                    saved[lk] = [x, y, w, h]
                    saved[rk] = [min(1.0 - w, max(0.0, 1.0 - (x + w))), y, w, h]
                except Exception:
                    pass
        for k, v in (saved or {}).items():
            if k in areas:
                areas[k] = norm_rect(v, areas[k])
            elif isinstance(v, (list, tuple)) and len(v) >= 4:
                areas[k] = norm_rect(v)          # 自定义区域也允许
        return areas
    except Exception:
        return areas


def has_areas(pet_id: str = None) -> bool:
    """这个角色**配过**触摸区域吗？

    和 `model.has_live2d`（角色包里有没有 Live2D 模型）同一套思路：
    触摸互动是逐角色做出来的东西 —— 只有做过坐标的角色才算"有"。
    没做过的角色不该凭空吃到一套"通用默认框"（对 Live2D 全身模型位置全错，
    还会把"点下半身开输入框"的老操作吃掉）。
    """
    try:
        from pets.pet_registry import get_pet_config
        cfg = get_pet_config(pet_id) or {}
        t = cfg.get("touch") or {}
        for k in ("areas_2d", "areas", "areas_live2d"):
            if isinstance(t.get(k), dict) and t[k]:
                return True
        return False
    except Exception:
        return False


def touch_enabled(pet_id: str = None) -> bool:
    """该角色现在是否启用全身触摸互动。

    规则（用户定的）：**没做过的角色一律不开**（照旧用 摸头 / 点下半身开输入框）；
    做过的角色看 pet.json 里的 touch.enabled，显式写死就照它，没写就默认开。
    """
    try:
        from pets.pet_registry import get_pet_config
        cfg = get_pet_config(pet_id) or {}
        t = cfg.get("touch") or {}
        v = t.get("enabled")
        if v is None:
            return has_areas(pet_id)
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("true", "1", "on", "yes")
    except Exception:
        return False


def set_enabled(pet_id: str, on: bool) -> bool:
    """写回角色包 pet.json 的 touch.enabled（"做了的可以选择开启/关闭"）"""
    try:
        from pets.pet_registry import get_pet_dir
        p = os.path.join(get_pet_dir(pet_id), "pet.json")
        if not os.path.exists(p):
            print(f"[Touch] ⚠ 角色配置不存在: {p}")
            return False
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        t = cfg.get("touch") or {}
        t["enabled"] = bool(on)
        cfg["touch"] = t
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("[Touch] %s全身触摸互动（%s）" % ("✅ 已开启" if on else "🚫 已关闭", pet_id))
        return True
    except Exception as e:
        print(f"[Touch] ⚠ 开关触摸失败: {e}")
        return False


def add_pet_area(pet_id: str, label: str, rect=None) -> str:
    """给角色加一个自定义部位（名字 + 默认框），返回新键；失败返回空串"""
    try:
        areas = get_pet_areas(pet_id)
        key = make_key(label, areas.keys())
        areas[key] = norm_rect(rect or [0.42, 0.20, 0.16, 0.10])
        labs = labels(pet_id)
        labs[key] = str(label or "新部位").strip() or "新部位"
        if save_pet_areas(pet_id, areas, labels=labs):
            print(f"[Touch] ➕ 已添加部位「{labs[key]}」（{key}）")
            return key
    except Exception as e:
        print(f"[Touch] ⚠ 添加部位失败: {e}")
    return ""


def remove_pet_area(pet_id: str, key: str) -> bool:
    """删掉一个自定义部位（默认 14 个不能删，避免按角色模板被清空）"""
    try:
        if str(key) in LABELS:
            print(f"[Touch] ⚠ 「{LABELS.get(str(key))}」是默认部位，不能删除（可改位置/大小）")
            return False
        areas = get_pet_areas(pet_id)
        areas.pop(str(key), None)
        labs = labels(pet_id)
        labs.pop(str(key), None)
        return bool(save_pet_areas(pet_id, areas, labels=labs))
    except Exception as e:
        print(f"[Touch] ⚠ 删除部位失败: {e}")
        return False


def save_pet_areas(pet_id: str, areas: dict, enabled: bool = None, labels: dict = None,
                   mode: str = "2d", disabled: list = None) -> bool:
    """写回角色包 pet.json 的 touch.areas（保留 pet.json 其余内容）"""
    try:
        from pets.pet_registry import get_pet_dir
        d = get_pet_dir(pet_id)
        p = os.path.join(d, "pet.json")
        if not os.path.exists(p):
            print(f"[Touch] ⚠ 角色配置不存在: {p}")
            return False
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        t = cfg.get("touch") or {}
        _mk = _mode_key(mode)
        t[_mk] = {k: norm_rect(v) for k, v in (areas or {}).items()}
        # 旧键同步一份（老版本/老工具仍读 touch.areas；2D 为准）
        if _mk == "areas_2d":
            t["areas"] = dict(t[_mk])
        if disabled is not None:
            t[_disabled_key(mode)] = [str(x) for x in disabled]
        # 自定义部位的名字（默认部位的显示名在代码里，不写文件）
        _labs = dict(labels or {})
        _all = {}
        for _k2 in ("areas_2d", "areas", "areas_live2d"):
            _all.update(t.get(_k2) or {})
        _custom = {k: str(v) for k, v in _labs.items() if k not in LABELS and k in _all}
        if _custom:
            t["labels"] = _custom
        else:
            t.pop("labels", None)
        if enabled is not None:
            t["enabled"] = bool(enabled)
        t.setdefault("enabled", True)
        cfg["touch"] = t
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"[Touch] ✅ 已保存 {len(t['areas'])} 个触摸区域 → {os.path.basename(p)}")
        return True
    except Exception as e:
        print(f"[Touch] ⚠ 保存触摸区域失败: {e}")
        return False
