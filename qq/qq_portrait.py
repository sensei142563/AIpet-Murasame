# -*- coding: utf-8 -*-
"""
Galgame 对话立绘 — 情绪 → 桌宠分层立绘合成（QQ 发送用）。

桌宠 fgimages 是「千恋万花·丛雨」的分层立绘素材：
每个编号是一张透明 PNG 图层（基础人物/表情/装饰/头发），带坐标索引 txt。
这里按情绪选层（固定校服装扮），用 alpha 合成完整立绘并保存 PNG，
供 QQ 消息作为图片发送。情绪词由对话模型按 Galgame 语境输出 [立绘:xxx]。
"""

import csv
import os
import sys
import threading

import cv2
import numpy as np

from pets.pet_registry import get_fgimages_dir, get_active_pet_id, get_pet_config

def _cn_name(n):
    """日文层名 → 中文显示名（立绘工坊/桌宠设置里的下拉用）"""
    try:
        from tool.jp_names import translate
        return translate(n)
    except Exception:
        return str(n)

_lock = threading.Lock()

# ── 情绪 → (表情层ID, 可选装饰层ID) ──────────────────────────
EMOTION_MAP = {
    # 开心/笑
    "开心": (1964, None), "高兴": (1964, None), "笑容": (1964, None),
    "笑": (1964, None), "嘿嘿": (1904, None), "得意": (1904, None),
    # 害羞/撒娇
    "害羞": (1480, 1958), "羞涩": (1480, 1958), "脸红": (1480, 1958),
    "撒娇": (1504, 1958), "腼腆": (1455, 1958),
    # 生气/不满
    "生气": (1620, None), "愤怒": (1620, None), "不满": (1801, None),
    # 难过/哭
    "难过": (1994, None), "伤心": (1994, None), "委屈": (1995, None),
    "哭": (1994, None),
    # 惊讶
    "惊讶": (1368, None), "震惊": (1368, None), "惊奇": (1368, None),
    # 思考/疑惑
    "思考": (1572, None), "疑惑": (1572, None), "困惑": (1572, None),
    # 平静/普通
    "平静": (1292, None), "普通": (1292, None), "正常": (1292, None),
    # 其它
    "严肃": (1822, None), "认真": (1822, None), "叹气": (1399, 1940),
    "累": (1399, None), "寂寞": (1528, None), "真挚": (1548, None),
    "紧张": (1935, None), "愣住": (1690, None), "孩子气": (1738, None),
    "窃笑": (1644, None), "恐惧": (1856, None), "焦急": (1399, None),
}
# 固定装扮（a 套校服·自然下垂 + 必选头发），保证合成稳定
_BASE_BODY = 1952
_HAIR = 1959
_CANVAS_W, _CANVAS_H = 3600, 5100

# ── 立绘工坊：可换的服装与装饰（a/b 两套立绘各自独立，见 tool/portrait_outfit.py）──
# a 套：制服1952 / 睡衣1956 / 私服1978 / 刀服1950（刀服配专用发型 1273）
# b 套：制服1716 / 睡衣1718 / 私服1717 / 刀服1715（发型统一 1261）
CLOTHES = [("制服（校服）", 1952, 1959), ("寝間着（睡衣）", 1956, 1959),
           ("私服（便服）", 1978, 1959), ("刀服（和装）", 1950, 1273)]   # a 套（兼容旧接口）
DECORS = [("脸红（頬）", 1958), ("叹气（息）", 1940)]                      # a 套（兼容旧接口）



def pet_portrait_cfg(pet_id=None) -> dict:
    """角色（默认当前活动角色）的 portrait 配置块；老角色没有则返回 {}"""
    try:
        from pets.pet_registry import get_pet_config
        pt = (get_pet_config(pet_id) or {}).get("portrait") or {}
        return pt if isinstance(pt, dict) and pt else {}
    except Exception:
        return {}


def _pt_block(pt, set_name=None):
    """角色 portrait 配置里「某一套」的选项表。

    新角色会分别给出 a/b 两套（portrait.sets.a / .b），层号完全不同（如芳乃 a 套校服 1860、
    b 套校服 1997）——一定要按当前套取，否则切到 b 套会拿着 a 套的层号去合成（等于没换衣服）。
    没有分套表时退回顶层（老配置兼容；向导写过 portrait.sets=["a"] 这种列表形式，也要认）。"""
    s = _set_of(set_name)
    sets = pt.get("sets")
    blk = (sets.get(s) or {}) if isinstance(sets, dict) else {}
    if blk:
        return blk
    return {k: pt.get(k) or {} for k in ("clothes", "emotions", "decors", "actions")}


def clothes_for(set_name=None, pet_id=None):
    """某套的服装选项 → [(显示名, 身体层 id, 发型层 id)]

    新角色（pet.json 有 portrait 块）：直接用角色自己的服装表；
    老角色：走内置表（行为不变）。"""
    pt = pet_portrait_cfg(pet_id)
    if pt:      # 新角色：以角色配置为准（没有服装就是空，不回退到内置表）
        blk = _pt_block(pt, set_name)
        return [(str(n), int((c or {}).get("cloth") or 0), int((c or {}).get("hair") or 0))
                for n, c in (blk.get("clothes") or {}).items()]
    from tool.portrait_outfit import clothes_of
    pretty = {"制服": "制服（校服）", "睡衣": "寝間着（睡衣）",
              "私服": "私服（便服）", "刀服": "刀服（和装）"}
    return [(pretty.get(n, n), c, h) for n, c, h in clothes_of(set_name)]


def decors_for(set_name=None, pet_id=None):
    """某套的装饰选项 → [(显示名, 层 id)]"""
    pt = pet_portrait_cfg(pet_id)
    if pt:
        blk = _pt_block(pt, set_name)
        return [(str(n), int(i)) for n, i in (blk.get("decors") or {}).items()
                if str(i).strip().isdigit()]
    from tool.portrait_outfit import decors_of
    return [((n + "（頬）") if n == "脸红" else n, i) for n, i in decors_of(set_name)]


def _pick_emotion_name(emo, emos):
    """模型给的情绪词（开心 / 害羞 / 生气…）→ 该角色表情表里最接近的一项。

    新角色（芳乃她们）的表情名是素材原样翻过来的（微笑 1 / 含羞的笑 / 平常 1…），
    跟 EMOTION_MAP 的中文情绪词并不一一对应；这里做一次语义就近匹配，
    否则桌宠/QQ 立绘只会在「默认表情」上不动。
    """
    if not emo or not emos:
        return ""
    if emo in emos:
        return emo

    def _find(subs):
        """命中多个时取「名字最短」的——基础表情比组合表情更像一张正常的情绪脸"""
        best = ""
        for sub in subs:
            for k in emos:
                if sub in k and (not best or len(k) < len(best)):
                    best = k
            if best:
                return best
        return best

    for kws, subs in _EMO_HINT:
        if any(k in emo for k in kws):
            got = _find(subs)
            if got:
                return got
    return ""


_EMO_HINT = (
    (("开心", "高兴", "笑", "嘿嘿", "得意", "俏皮", "高兴"),
     ("微笑", "笑容", "浅笑", "含笑", "坏笑", "笑")),
    (("害羞", "羞涩", "脸红", "腼腆", "撒娇", "不好意思"),
     ("害羞", "脸红", "含羞", "垂头", "娇")),
    (("生气", "愤怒", "不满", "怒", "凶", "瞪"),
     ("生气", "不满", "怒气", "怒", "鼓脸", "气鼓鼓", "可怕")),
    (("难过", "伤心", "委屈", "哭", "寂寞", "悲", "失落"),
     ("泪水", "悲伤", "寂寞", "垂头", "哭脸", "忧愁")),
    (("惊讶", "震惊", "惊奇", "意外", "吃惊"),
     ("惊讶", "睁大", "瞪大", "发愣")),
    (("思考", "疑惑", "困惑", "疑问", "沉思"),
     ("沉思", "疑惑", "狐疑", "解说")),
    (("紧张", "着急", "焦急", "慌", "急"),
     ("紧张", "慌张", "着急", "慌")),
    (("平静", "普通", "正常", "冷静", "安心"),
     ("基础", "平常", "平静", "从容", "浅笑")),
    (("困", "睡", "累"),
     ("困倦", "睡眼", "困")),
    (("无奈", "叹气", "叹气", "苦"),
     ("无奈", "叹气", "基础", "平常")),
)


_PLAIN_HINT = ("微笑", "笑容", "浅笑", "含笑", "平常", "基础", "平静", "从容", "认真", "发愣")


def _plain_emotion(emos) -> str:
    """表情表里的「基础那张脸」：优先 微笑/平常/基础 这类中性表情，再退而求最短的非组合表情"""
    plain = [k for k in emos if "组合表情" not in k] or list(emos)
    if not plain:
        return ""
    for hint in _PLAIN_HINT:
        hit = [k for k in plain if hint in k]
        if hit:
            return min(hit, key=len)
    return min(plain, key=len)


def actions_for(set_name=None, pet_id=None):
    """某套的动作（手臂姿势）选项 → [(显示名, 动作层 id, 所属服装层 id)]

    动作 = 同一件衣服的另一种手臂姿势（素材里的「腕差分」）。"""
    try:
        from tool.portrait_outfit import actions_of
        return [(str(n), int(a), int(b)) for n, a, b in actions_of(_set_of(set_name), pet_id)]
    except Exception:
        return []


def cross_set_layers(layers, dst_set) -> list:
    """把任意套的图层换算到 dst_set（供桌宠灵动切换 / 历史图层复用）"""
    from tool.portrait_outfit import normalize_layers
    return normalize_layers(layers, dst_set)

_cache = {}   # {套装: {infos, dir, prefix, rows}}


def _choice_path():
    try:
        from tool.portrait_outfit import choice_path
        return choice_path()
    except Exception:
        return os.path.join("data", "portrait_choice.json")


def load_choice(set_name=None) -> dict:
    """读取指定套装（默认当前 active 套）的装扮 → 统一模块"""
    try:
        from tool.portrait_outfit import load_outfit
        return load_outfit(set_name)
    except Exception:
        return {"set": set_name or "a", "cloth": "制服", "cloth_id": _BASE_BODY,
                "hair": _HAIR, "decor": []}


def save_choice(cloth, hair=None, decor=None, set_name=None, action=None, scene=None,
                emotion=None) -> bool:
    """保存装扮（转发统一模块；桌宠模式与 QQ 立绘共用同一份配置）

    action：动作（手臂姿势）名或层号；None = 保持原样，0 = 回到默认姿势。"""
    try:
        from tool.portrait_outfit import save_outfit
        return save_outfit(cloth, hair, decor, set_name=set_name, action=action,
                           scene=scene, emotion=emotion)
    except Exception as e:
        print(f"[QQPortrait] ⚠ 保存立绘装扮失败: {e}", file=sys.stderr)
        return False


def _available_sets() -> list:
    """当前角色实际有素材的立绘套（扫描 fgimages 里的 {prefix}{set}.txt）。"""
    try:
        fg_dir, prefix = _resolve_dir()
        if not fg_dir or not os.path.isdir(fg_dir):
            return []
        out = []
        for f in sorted(os.listdir(fg_dir)):
            if f.startswith(prefix) and f.endswith(".txt"):
                s = f[len(prefix):-4]
                if s and s not in out:
                    out.append(s)
        return out
    except Exception:
        return []


def _set_of(set_name=None) -> str:
    """当前要用的立绘体系：显式指定 > 配置里的 active > a

    ⚠ active 是全局配置（可能是丛雨的 b 套）；新角色只有 a 套时必须回落到
    角色自己有的套，否则会去找 {prefix}b.txt（不存在）→ 立绘空白/合成失败。
    """
    try:
        from tool.portrait_outfit import active_set, SETS
        s = str(set_name or "").strip().lower()
        want = s if s in SETS else active_set()
    except Exception:
        want = "a"
    avail = _available_sets()
    if avail and want not in avail:
        print(f"[Portrait] ℹ 角色没有 {want} 套立绘（可用: {avail}）→ 用 {avail[0]}", file=sys.stderr)
        return avail[0]
    return want


# ══════════ 本地场景背景（替代联网搜背景）══════════
# 场景素材默认放在项目目录内的「场景素材」文件夹（随安装包一起分发，开箱即用）
# 想换位置：config.json 里设置 portrait_scene_dir 指向自己的文件夹
_SCENE_DIR_FALLBACK = r"D:\下载\AI桌宠\场景"     # 旧版素材来源（项目内目录不存在时兜底）


def _project_scene_dir() -> str:
    """项目目录内的默认场景素材文件夹"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "场景素材")


SCENE_DIR_DEFAULT = _project_scene_dir()
STD_W, STD_H = 1280, 720   # 场景统一画布（长方形 16:9；其它比例的图自动裁剪/拉伸防黑边）
SCENE_ZOOM = 1.45          # 场景放大系数（视野更近；裁剪式放大，绝不出现黑边）
PERSON_FILL = 0.99         # 人物高度占画布比例（≈满屏，头顶不裁切）
HALF_RATIO = 0.56          # 半身裁剪比例（越小=人物越大，头肩更近）
_SCENE_LAST = {"path": ""}


def scene_dir() -> str:
    """场景素材目录（优先级：config.portrait_scene_dir > 项目内「场景素材」 > 旧素材目录）"""
    try:
        from tool.config import get_config
        d = str(get_config("./config.json").get("portrait_scene_dir") or "").strip()
        if d and os.path.isdir(d):
            return d
    except Exception:
        pass
    if os.path.isdir(SCENE_DIR_DEFAULT):
        return SCENE_DIR_DEFAULT
    return _SCENE_DIR_FALLBACK


def list_scenes():
    """场景目录（含子目录）下所有图片文件"""
    out = []
    d = scene_dir()
    if os.path.isdir(d):
        for root, _dirs, files in os.walk(d):
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
                    out.append(os.path.join(root, f))
    return sorted(out)


def _cover_scene(img, zoom=SCENE_ZOOM):
    """场景图 cover 到标准画布：按比例缩放铺满 + 中心裁剪，任何尺寸都不出黑边。
    再做 zoom 放大（中心裁剪后拉回原尺寸）→ 场景更大更近，超出部分裁切。
    统一转 BGRA（人物合成用 4 通道，3 通道会索引越界）。"""
    h, w = img.shape[:2]
    scale = max(STD_W / max(1, w), STD_H / max(1, h))
    nw, nh = max(STD_W, int(w * scale + 0.5)), max(STD_H, int(h * scale + 0.5))
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    x0 = (nw - STD_W) // 2
    y0 = (nh - STD_H) // 2
    out = img[y0:y0 + STD_H, x0:x0 + STD_W].copy()
    # zoom：中心取 1/zoom 区域放大回画布（裁剪式放大，不产生黑边）
    if zoom and zoom > 1.0:
        zw, zh = int(STD_W / zoom), int(STD_H / zoom)
        zx = (STD_W - zw) // 2
        zy = (STD_H - zh) // 2
        out = cv2.resize(out[zy:zy + zh, zx:zx + zw], (STD_W, STD_H),
                         interpolation=cv2.INTER_CUBIC)
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGRA)
    elif out.shape[2] == 3:
        out = cv2.cvtColor(out, cv2.COLOR_BGR2BGRA)
    return out


def _scene_bg(scene_path=None):
    """取一张本地场景图作为背景：
    - scene_path 指定时用该图；
    - None 时随机（避免与上次重复）；
    - 无场景返回 None。"""
    import random as _rnd
    p = str(scene_path or "").strip()
    if not p or not os.path.exists(p):
        scenes = list_scenes()
        if not scenes:
            return None
        pool = [x for x in scenes if x != _SCENE_LAST["path"]] or scenes
        p = _rnd.choice(pool)
    img = None
    try:
        img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is None:
        return None
    _SCENE_LAST["path"] = p
    return _cover_scene(img)


def expression_choices(set_name=None):
    """立绘工坊的表情选项 → [(显示名, 表情层id)]
    中文情绪名优先（EMOTION_MAP 换算到该套），再补充该套索引里其它表情层（日文原名）。"""
    s = _set_of(set_name)
    out = []
    seen_ids = set()
    # 新角色：表情选项来自角色自己的 portrait 配置（按当前套取，a/b 层号不同）
    pt = pet_portrait_cfg()
    _em = (pt.get("emotions") or {}) if not pt.get("sets") else _pt_block(pt, s).get("emotions")
    if _em:
        for cn, lid in _em.items():
            try:
                lid = int(lid)
            except Exception:
                continue
            if lid and lid not in seen_ids:
                seen_ids.add(lid)
                out.append((str(cn), lid))
        if out:
            return out
    try:
        from tool.portrait_outfit import translate_layers
        for cn, (lid, _d) in EMOTION_MAP.items():
            tid = lid if s == "a" else ((translate_layers([lid], "a", s) or [0])[0])
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
            out.append((cn, tid))
    except Exception:
        pass
    try:
        info = _load_index(s)
        grp = {"a": ("1941", "1984", "1977"), "b": ("1705", "1743", "1734")}.get(s, ())
        for x in (info.get("rows") or []):
            if len(x) > 10 and x[10].strip() in grp and x[9].strip().isdigit():
                lid = int(x[9].strip())
                if lid in seen_ids:
                    continue
                seen_ids.add(lid)
                nm = _cn_name(x[1].strip() or f"表情{lid}")
                out.append((_uniq_name(out, nm[:18], lid), lid))
    except Exception:
        pass
    return out


def _uniq_name(pairs, name, lid) -> str:
    """下拉显示名去重：同名时补上层号，避免两个选项看起来一模一样"""
    used = {str(n) for n, _i in pairs}
    if name not in used:
        return name
    cand = f"{name}（{lid}）"
    i = 2
    while cand in used:
        cand = f"{name}（{lid}-{i}）"
        i += 1
    return cand


def compose_custom(cloth, hair, expr, decors=None, out_name="qq_portrait_studio.png",
                   scene=None, set_name=None, full_body=False, no_bg=False) -> str:
    """立绘工坊预览：按指定套装/服装/发型/表情/装饰合成一张立绘图，返回路径。
    - set_name：a / b 立绘体系（默认配置里的 active 套）
    - scene：指定场景图路径（None=随机场景），与 build_portrait 同一套合成逻辑。"""
    layers = [int(cloth), int(expr), int(hair)]
    for d in (decors or []):
        if int(d) not in layers:
            layers.append(int(d))
    return build_portrait("", "", _layers=layers, out_name=out_name,
                          _scene=scene, set_name=set_name,
                          full_body=full_body, no_bg=no_bg)


def emotion_words() -> str:
    """给模型的可用情绪词列表（去重保序）"""
    seen = []
    for k in EMOTION_MAP:
        if k not in seen:
            seen.append(k)
    return "、".join(seen)


def _resolve_dir():
    pet_id = get_active_pet_id()
    fg_dir = get_fgimages_dir(pet_id)
    # 前缀统一解析：model.fgimages_prefix → portrait.prefix → 角色ID（绝不为空）
    try:
        from pets.pet_registry import get_fgimages_prefix
        prefix = get_fgimages_prefix(pet_id)
    except Exception:
        cfg = get_pet_config(pet_id)
        prefix = (cfg.get("model") or {}).get("fgimages_prefix", "") or "ムラサメ"
    return fg_dir, prefix


def _load_index(set_name="a"):
    """读 {prefix}{set}.txt(UTF-16 TSV) → {layer_id: (left, top, w, h)}（每套各自缓存）"""
    key = _set_of(set_name)
    with _lock:
        if _cache.get(key):
            return _cache[key]
        fg_dir, prefix = _resolve_dir()
        idx_path = os.path.join(fg_dir, f"{prefix}{key}.txt")
        infos, rows = {}, []
        if os.path.exists(idx_path):
            try:
                # 编码容错：优先 utf-16（含 BOM），失败回退 utf-16-le / utf-8，
                # 保证中文/日文图层名不会被解成乱码
                _enc = "utf-16"
                try:
                    with open(idx_path, "rb") as fb:
                        head = fb.read(2)
                    if head[:2] == b"\xff\xfe" or head[:2] == b"\xfe\xff":
                        _enc = "utf-16"
                    else:
                        _enc = "utf-16 le"
                except Exception:
                    _enc = "utf-16"
                with open(idx_path, encoding=_enc, errors="replace") as f:
                    rows = list(csv.reader(f, delimiter="\t"))
                for x in rows:
                    if len(x) >= 10 and x[9].strip().isdigit():
                        try:
                            infos[int(x[9])] = (int(x[2]), int(x[3]),
                                                int(x[4]), int(x[5]))
                        except Exception:
                            pass
            except Exception as e:
                print(f"[QQPortrait] ⚠ 读取 {key} 套图层索引失败: {e}", file=sys.stderr)
        _cache[key] = {"set": key, "infos": infos, "dir": fg_dir,
                       "prefix": prefix, "rows": rows}
        return _cache[key]


def _paste(canvas, img, left, top):
    """把 img 贴到 canvas 的 (left, top)。left/top 可以是负数（图层超出画布左上角）——
    以前直接 canvas[top:y2, left:x2]，负 left 会被 numpy 当成「从末尾数」→ 切成空数组
    → 报 operands could not be broadcast together（立绘工坊「合成失败」的真凶）。"""
    h, w = img.shape[:2]
    sx = max(0, -int(left))          # 源图要裁掉的左边/上边
    sy = max(0, -int(top))
    dx = max(0, int(left))           # 画布上的起点
    dy = max(0, int(top))
    w = min(w - sx, canvas.shape[1] - dx)
    h = min(h - sy, canvas.shape[0] - dy)
    if w <= 0 or h <= 0:
        return
    reg_img = img[sy:sy + h, sx:sx + w]
    reg_can = canvas[dy:dy + h, dx:dx + w]
    a_img = reg_img[..., 3:4] / 255.0
    a_can = 1.0 - a_img
    for c in range(3):
        reg_can[..., c] = a_img[..., 0] * reg_img[..., c] + a_can[..., 0] * reg_can[..., c]
    reg_can[..., 3] = np.maximum(reg_img[..., 3], reg_can[..., 3])


def _read_layer(fg_dir, prefix, set_name, layer_id):
    p = os.path.join(fg_dir, f"{prefix}{set_name}_{layer_id}.png")
    if not os.path.exists(p):
        return None
    img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    return img if img is not None else None


# 话题 → 背景搜索词（联网找背景用；未命中时用默认渐变背景）
BG_KEYWORDS = {
    "公园": "公园 湖 风景", "海边": "海边 沙滩 蓝天", "大海": "海边 浪花", "沙滩": "沙滩 海",
    "夜景": "城市 夜景", "晚上": "夜景 星空", "星空": "星空 夜晚", "学校": "学校 操场",
    "教室": "教室 黑板", "房间": "温馨 房间 窗", "卧室": "卧室 温馨", "客厅": "客厅 沙发",
    "咖啡": "咖啡馆 下午茶", "餐厅": "餐厅 美食", "街道": "城市 街道 夜景", "城市": "城市 街景",
    "樱花": "樱花 场景", "神社": "神社 日本", "森林": "森林 阳光", "草地": "草地 天空",
    "天空": "蓝天 白云", "雪": "雪景 白色", "温泉": "温泉 露天", "夏日": "夏日 海滩",
    "夏天": "夏日 蝉 绿荫", "雨": "雨景 窗", "雨天": "雨天 街道", "黄昏": "黄昏 晚霞",
    "夕阳": "夕阳 海边", "月亮": "夜晚 月亮", "花园": "花园 花", "操场": "操场 学校",
    "天台": "天台 天空", "山顶": "山顶 云海", "家乡": "乡村 田园", "田野": "田园 田野",
}


def extract_bg_kw(text: str) -> str:
    """从对话文本粗略提取话题场景词（供立绘背景搜索）；无命中返回空串"""
    t = text or ""
    for k, q in BG_KEYWORDS.items():
        if k in t:
            return q
    return ""


def _default_bg(h=880, w=720):
    """默认立绘背景：柔和竖向渐变（粉白→淡蓝），避免透明空白"""
    top = np.array([255, 240, 248], dtype=np.float32)   # 淡粉
    mid = np.array([240, 244, 255], dtype=np.float32)   # 淡蓝
    grad = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(h):
        t = y / max(1, h - 1)
        if t < 0.6:
            c = top + (mid - top) * (t / 0.6)
        else:
            c = mid + (np.array([255, 255, 255], dtype=np.float32) - mid) * ((t - 0.6) / 0.4)
        grad[y, :, :] = c
    bg = np.zeros((h, w, 4), dtype=np.uint8)
    bg[..., :3] = grad.astype(np.uint8)
    bg[..., 3] = 255
    return bg


def _search_bg(kw):
    """联网找背景图 → 返回 720x880(cover 裁切) BGRA；失败返回 None"""
    try:
        from qq.qq_search import search_images
        import requests as _req
        imgs = search_images(kw + " 背景", 2) or search_images(kw, 2)
        for im in imgs:
            u = im.get("url")
            if not u:
                continue
            try:
                r = _req.get(u, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"})
                if r.status_code != 200 or len(r.content) < 2000:
                    continue
                arr = np.frombuffer(r.content, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
                if img is None:
                    continue
                if img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                # cover 裁切到 720x880
                ih, iw = img.shape[:2]
                scale = max(720.0 / iw, 880.0 / ih)
                img = cv2.resize(img, (int(iw * scale + 0.5), int(ih * scale + 0.5)),
                                 interpolation=cv2.INTER_AREA)
                ih2, iw2 = img.shape[:2]
                x0 = (iw2 - 720) // 2
                y0 = (ih2 - 880) // 2
                return img[y0:y0 + 880, x0:x0 + 720].copy()
            except Exception:
                continue
    except Exception:
        pass
    return None


def _with_scene_bg(_scene, half):
    """把人物贴到本地场景背景上（长方形画布，cover 裁剪 + 放大防黑边；无场景回退默认渐变）。

    注意：这是**立绘工坊 / QQ 立绘**用的带背景合成；桌宠设置与触摸调节的预览
    用的是 full_body + no_bg（全身、透明底），不走这里。"""
    # ── 背景：本地场景目录（长方形画布，cover 裁剪 + 放大防黑边）；无场景回退默认渐变 ──
    bg = _scene_bg(_scene)
    if bg is None:
        OUT_W, OUT_H = STD_W, STD_H
        bg = _default_bg(OUT_H, OUT_W)
    out = bg.copy()
    OUT_H, OUT_W = out.shape[:2]
    # 人物放大贴底：高度 ~OUT_H*PERSON_FILL（≈满屏高，头顶不裁切），水平居中
    ph, pw = half.shape[:2]
    target_h = int(OUT_H * PERSON_FILL)
    scale = min(target_h / ph, (OUT_W * 1.15) / pw)
    nw, nh = int(pw * scale), int(ph * scale)
    person = cv2.resize(half, (nw, nh), interpolation=cv2.INTER_AREA)
    px = (OUT_W - nw) // 2
    py = OUT_H - nh
    # 允许两侧超出画布（放大后裁切，不留黑边）
    if py < 0:
        person = person[-py:, :]
        nh += py
        py = 0
    if px < 0:
        person = person[:, -px:]
        nw += px
        px = 0
    if px + nw > OUT_W:
        person = person[:, :OUT_W - px]
        nw = OUT_W - px
    if py + nh > OUT_H:
        person = person[:OUT_H - py, :]
        nh = OUT_H - py
    a = person[..., 3:4] / 255.0
    a2 = 1.0 - a
    reg = out[py:py + nh, px:px + nw]
    for c in range(3):
        reg[..., c] = (a[..., 0] * person[..., c] + a2[..., 0] * reg[..., c])
    reg[..., 3] = np.maximum(person[..., 3], reg[..., 3])
    return out


def build_portrait(emotion: str = "", bg_kw: str = "",
                   _layers=None, out_name: str = "qq_portrait_latest.png",
                   _scene=None, set_name=None,
                   full_body: bool = False, no_bg: bool = False) -> str:
    """按情绪合成一张【半身】立绘 PNG（带本地场景背景），返回文件路径。

    - set_name：a / b 两套立绘体系（默认读配置里的 active 套）；
      a 套与 b 套的服装/表情图层 ID 完全不同，各自成套、互不串用；
    - 半身：只取全身立绘的上部（头部+上半身，HALF_RATIO 控制）；
    - 背景：从本地场景目录取图（_scene 指定具体图，None=随机），
      统一 1280x720 长方形画布 + 中心裁剪 + SCENE_ZOOM 放大，任何尺寸都不出黑边；
    - 装扮：用该套在「立绘工坊」保存的服装/装饰（未保存则制服）；
      情绪仍按 emo 自动变化；
    - _layers/out_name/_scene：立绘工坊预览用（指定层组合、输出名与场景）；
    - full_body=True：不裁上半身，保留**全身**（桌宠设置 / 触摸调节的预览用）；
    - no_bg=True：不贴场景背景，输出**透明底**（同上；立绘工坊仍用带背景的半身）。"""
    try:
        s = _set_of(set_name)
        emo = (emotion or "").strip()
        # 新角色：情绪→图层的映射来自 pet.json 的 portrait 块（按当前套取，a/b 层号不同）
        _pt = pet_portrait_cfg()
        _has_pt = bool(_pt.get("emotions") or _pt.get("sets"))
        if _has_pt:
            _emos = {str(k): v for k, v in ((_pt_block(_pt, s).get("emotions")) or {}).items()}
            _nm = _pick_emotion_name(emo, _emos)
            _lid = (_emos.get(_nm) or _emos.get(str(_pt.get("default_emotion") or ""))
                    or _emos.get(_plain_emotion(_emos)) or next(iter(_emos.values()), 0))
            try:
                emo_id, decor_id = int(_lid or 0), None
            except Exception:
                emo_id, decor_id = 0, None
        else:
            emo_id, decor_id = EMOTION_MAP.get(emo, EMOTION_MAP.get("平静", (1292, None)))
            if s != "a":           # 老角色：a 套层号 → b 套层号（新角色两套各有一套表，不用换算）
                from tool.portrait_outfit import translate_layers
                _tr = translate_layers([x for x in (emo_id, decor_id) if x], "a", s)
                emo_id = _tr[0] if _tr else 0
                decor_id = _tr[1] if decor_id and len(_tr) > 1 else None
        info = _load_index(s)
        fg_dir, prefix = info["dir"], info["prefix"]
        infos = info["infos"]
        # 单图模式（向导创建的「每个表情一张整图」角色）：一张图就是完整立绘，
        # 不能再叠服装/发型层，否则会串图。
        if _pt.get("mode") == "single" and _layers is None:
            _layers = [int(x) for x in ([emo_id] if emo_id else []) if int(x or 0) > 0]
        if _layers is None:
            # 该套保存的装扮（服装+动作+配套发型+装饰） + 当前情绪表情
            ch = load_choice(s)
            # 选了动作（换臂姿势）就用动作层当身体层；它是同一件衣服的另一种手臂姿势
            body_id = int(ch.get("action_id") or 0) or int(ch["cloth_id"])
            layers = [body_id, emo_id, ch["hair"]]
            if decor_id:
                layers.append(decor_id)
            for d in ch["decor"]:
                if d not in layers:
                    layers.append(d)
        else:
            layers = list(_layers)
        # 防御：传入的图层若是另一套的 ID → 自动换算到本套（历史图层/AI 越界复用不崩）
        # 但两套的层号是可能重复的（如蕾娜 a/b 都有 304），只要本套索引里能找到这个层号，
        # 就说明它本来就是本套的层，绝不能再去「翻译」（否则会翻成空层 → 合成空白）。
        _missing = [l for l in layers if l and l not in infos]
        if _missing:
            try:
                from tool.portrait_outfit import normalize_layers
                layers = normalize_layers(layers, s)
            except Exception:
                pass
        canvas = np.zeros((_CANVAS_H, _CANVAS_W, 4), dtype=np.uint8)
        # 图层微调（防穿模）：网页版/QQ 立绘与桌面立绘共用同一份设置
        try:
            from tool.generate import _adjust_table, _category_of
            _adj = _adjust_table(get_active_pet_id(), s)
        except Exception:
            _adj = {}
        # ★ 绘制顺序：阴影类装饰要画在表情下面（否则盖住五官）
        try:
            from tool.portrait_outfit import order_for_draw
            _nm = {}
            for x in (info.get("rows") or []):
                if len(x) > 9:
                    _nm[str(x[9])] = x[1]
            layers = order_for_draw(layers, names=_nm)
        except Exception as _e:
            print(f"[QQPortrait] ⚠ 图层排序跳过: {_e}")
        for lid in layers:
            pos = infos.get(lid)
            img = _read_layer(fg_dir, prefix, s, lid)
            if pos and img is not None:
                _paste(canvas, img, pos[0], pos[1])
        alpha = canvas[..., 3]
        ys, xs = np.where(alpha > 0)
        if len(xs) == 0:
            # 自己把原因写清楚：少了哪个图层、素材目录/前缀对不对，省得只知道「合成失败」
            try:
                _miss = [l for l in layers if l not in infos]
                _nofile = [l for l in layers if infos.get(l) and
                           not os.path.exists(os.path.join(fg_dir, f"{prefix}{s}_{l}.png"))]
                print(f"[QQPortrait] ⚠ 合成结果为空（情绪 {emo} / {s} 套）"
                      f" | 素材目录={fg_dir} | 前缀={prefix!r} | 索引层数={len(infos)}"
                      f" | 请求图层={layers} | 索引里没有的={_miss} | 有索引但没图片的={_nofile}",
                      file=sys.stderr)
            except Exception:
                print(f"[QQPortrait] ⚠ 合成结果为空（情绪 {emo} / {s} 套）图层={layers}", file=sys.stderr)
            return ""
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        full = canvas[y0:y1 + 1, x0:x1 + 1]
        fh, fw = full.shape[:2]
        if full_body:
            # 全身：不裁上半身（桌宠设置 / 触摸区域调节的预览）
            half = full.copy()
        else:
            # ── 半身：保留上部 HALF_RATIO（头+上半身），越小人物越大 ──
            half_h = int(fh * HALF_RATIO)
            half = full[:half_h, :, :].copy()
        if no_bg:
            # 透明底：画面就是人物本身（不放大、不贴场景）
            out = half
        else:
            out = _with_scene_bg(_scene, half)
        if out is None or out.size == 0:
            return ""
        out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "tmp")
        os.makedirs(out_dir, exist_ok=True)
        out_p = os.path.join(out_dir, out_name)
        # 原子写：先写唯一临时名再替换 —— 避免预览图正被查看器/资源管理器占用时写失败
        tmp_p = f"{out_p}.tmp{os.getpid()}"
        try:
            cv2.imencode(".png", out)[1].tofile(tmp_p)
            os.replace(tmp_p, out_p)
        except Exception:
            try:
                if os.path.exists(tmp_p):
                    os.remove(tmp_p)
            except Exception:
                pass
            # 原子替换失败则退回直接写（至少尽力产出）
            cv2.imencode(".png", out)[1].tofile(out_p)
        return out_p
    except Exception as e:
        print(f"[QQPortrait] ⚠ 立绘合成失败: {e}", file=sys.stderr)
        return ""
