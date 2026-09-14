# -*- coding: utf-8 -*-
"""立绘装扮（服装/装饰）统一模块 —— 桌宠模式与 QQ 立绘共用同一份配置。

存储：data/portrait_choice.json
  {
    "active": "a",                        # 当前使用的立绘体系（QQ 立绘 / 桌宠启动时用）
    "a": {"cloth": "制服", "decor": []},   # a 套自己的服装与装饰
    "b": {"cloth": "制服", "decor": []}    # b 套自己的服装与装饰
  }

服装只存【名字】，ID 按套装解析——a/b 两套素材服装层完全独立：
  a 套：制服1952 / 睡衣1956 / 私服1978 / 刀服1950（发型 1959；刀服 1273）
  b 套：制服1716 / 睡衣1718 / 私服1717 / 刀服1715（发型统一 1261）
这样 a 套立绘绝不会用到 b 套的服装层，反之亦然。

用途：
- QQ 发送的立绘（qq_portrait.build_portrait）按 active 套的装扮合成；
- 桌宠 2D 立绘（classes/murasame_class.update_portrait）按当前显示套的装扮替换身体层；
- 桌宠右键菜单 / 立绘工坊 / AI 换装标记都调用 save_outfit 写同一份配置，
  因此"在哪换装，其它地方都同步生效"；
- translate_layers() 负责两套之间的图层换算（情绪/服装/头发/装饰），
  供桌宠"回复时概率切换立绘类型"的灵动效果与历史图层复用。
"""
import csv
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SETS = ("a", "b")
DEFAULT_SET = "a"

# ── 服装：显示名 → (身体层 id, 配套发型层 id)，按套装各自独立 ──
CLOTH_ORDER = ["制服", "睡衣", "私服", "刀服"]
CLOTHES_BY_SET = {
    "a": {
        "制服": (1952, 1959),
        "睡衣": (1956, 1959),
        "私服": (1978, 1959),
        "刀服": (1950, 1273),   # 刀服需配专用发型
    },
    "b": {
        "制服": (1716, 1261),
        "睡衣": (1718, 1261),
        "私服": (1717, 1261),
        "刀服": (1715, 1261),
    },
}
# ── 装饰（各套素材不同）──
DECORS_BY_SET = {
    "a": {"脸红": 1958, "叹气": 1940},
    "b": {"脸红": 1719, "不满": 1708},
}
# 别名（口语 / AI 换装标记 → 标准名）
CLOTH_ALIASES = {
    "制服": "制服", "校服": "制服", "学生装": "制服", "学生服": "制服",
    "睡衣": "睡衣", "寝間着": "睡衣", "寝间着": "睡衣", "睡袍": "睡衣", "寝衣": "睡衣",
    "私服": "私服", "便服": "私服", "便衣": "私服", "常服": "私服", "休闲装": "私服",
    "刀服": "刀服", "和装": "刀服", "和服": "刀服", "刀装": "刀服", "便衣2": "刀服",
}
DEFAULT_CLOTH = "制服"

# 每套的服装层集合 / 发型层集合（识别旧图层并替换用）
BODY_LAYERS_BY_SET = {s: {v[0] for v in m.values()} for s, m in CLOTHES_BY_SET.items()}
HAIR_LAYERS_BY_SET = {s: {v[1] for v in m.values()} for s, m in CLOTHES_BY_SET.items()}
for _s in SETS:
    for _i in DECORS_BY_SET[_s].values():
        HAIR_LAYERS_BY_SET[_s].discard(_i)

# 两套的表情"基准脸"（翻译兜底用）
EXPR_FALLBACK = {"a": 1292, "b": 1306}

# a 套表情名 → b 套表情名（没有同名时的人工对应）
_EXPR_NAME_ALIAS = {
    "笑顔1": "笑顔2", "きょとん": "驚き", "焦る": "目を見開き驚く", "焦る2": "目を見開き驚く",
    "照れ": "恥ずかしい", "照れる": "恥ずかしい", "照れる2": "恥ずかしい",
    "寂しい": "悲しい", "考える": "真剣", "困った": "悲しい", "怒り": "怒り叫び",
    "にやにや": "微笑み", "にやにや2": "微笑み", "呆れ": "ジト目", "訝しむ": "ジト目",
    "子供っぽい": "拗ねる", "最大限に不満": "ぐぬぬ", "最大限に不満げ": "ぐぬぬ2",
    "真面目な顔": "真面目な顔2", "恐怖": "目を見開き驚く", "えへへ": "笑顔2",
    "緊張": "真剣",
}
# 涙 / 追加表情组的逐层对应（名字不成对，只能人工映射）
_EXTRA_ID_MAP_A2B = {
    # a 涙 → b 涙
    1996: 1755, 1995: 1754, 1994: 1753, 1993: 1752, 1992: 1751, 1991: 1750,
    2009: 1749, 1989: 1748, 1988: 1747, 1987: 1745, 1986: 1765,
    # a 追加 → b 追加
    1964: 1721, 1963: 1722, 1965: 1722, 1966: 1725, 1967: 1723, 1968: 1728,
    1969: 1729, 1970: 1730, 1971: 1733, 1972: 1728, 1973: 1731, 1974: 1727,
    1975: 1727, 1976: 1724,
}

_trans_cache = {}
_index_cache = {}


# ══════════ 配置读写 ══════════
def choice_path() -> str:
    try:
        from tool.paths import data_path
        return os.path.join(data_path("data"), "portrait_choice.json")
    except Exception:
        return os.path.join(BASE_DIR, "data", "portrait_choice.json")


def _default_entry(set_name: str) -> dict:
    return {"cloth": DEFAULT_CLOTH, "decor": []}


def _legacy_cloth_name(cloth_id) -> str:
    """旧配置存的是服装层 ID（仅 a 套）→ 名字"""
    try:
        cid = int(cloth_id)
    except Exception:
        return DEFAULT_CLOTH
    for s in SETS:
        for n, (c, _h) in CLOTHES_BY_SET[s].items():
            if c == cid:
                return n
    return DEFAULT_CLOTH


def _raw_load() -> dict:
    """读原始配置并归一化（含旧格式迁移）"""
    data = {}
    try:
        p = choice_path()
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                data = json.load(f) or {}
    except Exception:
        data = {}
    out = {"active": str(data.get("active") or DEFAULT_SET)}
    if out["active"] not in SETS:
        out["active"] = DEFAULT_SET
    for s in SETS:
        ent = data.get(s)
        if isinstance(ent, dict):
            cloth = str(ent.get("cloth") or DEFAULT_CLOTH)
            if cloth.isdigit():          # 万一存成 ID
                cloth = _legacy_cloth_name(cloth)
            if cloth not in CLOTHES_BY_SET[s]:
                cloth = _legacy_cloth_name(cloth) if cloth.isdigit() else DEFAULT_CLOTH
            if cloth not in CLOTHES_BY_SET[s]:
                cloth = DEFAULT_CLOTH
            decors = []
            for x in (ent.get("decor") or []):
                try:
                    xi = int(x)
                except Exception:
                    continue
                if xi in set(DECORS_BY_SET[s].values()):
                    decors.append(xi)
            out[s] = {"cloth": cloth, "decor": decors}
        else:
            out[s] = _default_entry(s)
    # 旧扁平格式：{"cloth": 1978, "hair": 1959, "decor": [1958]}（a 套）
    if "cloth" in data and not any(isinstance(data.get(s), dict) for s in SETS):
        out["active"] = DEFAULT_SET
        out["a"] = {"cloth": _legacy_cloth_name(data.get("cloth")),
                    "decor": [int(x) for x in (data.get("decor") or [])
                              if str(x).lstrip("-").isdigit()] or []}
    return out


def _raw_save(d: dict) -> bool:
    try:
        p = choice_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        return True
    except Exception as e:
        print(f"[PortraitOutfit] ⚠ 保存装扮失败: {e}")
        return False


def active_set() -> str:
    """当前使用的立绘体系（QQ 立绘 / 桌宠启动）"""
    return _raw_load()["active"]


def set_active(set_name: str) -> bool:
    s = str(set_name or "").strip().lower()
    if s not in SETS:
        return False
    d = _raw_load()
    if d["active"] == s:
        return True
    d["active"] = s
    return _raw_save(d)


# ══════════ 选项枚举 ══════════
def clothes_of(set_name=None):
    """某套的服装选项 → [(名字, 身体层 id, 发型层 id)]"""
    s = set_name or active_set()
    m = CLOTHES_BY_SET.get(s, CLOTHES_BY_SET[DEFAULT_SET])
    return [(n, m[n][0], m[n][1]) for n in CLOTH_ORDER if n in m]


def decors_of(set_name=None):
    """某套的装饰选项 → [(名字, 层 id)]"""
    s = set_name or active_set()
    m = DECORS_BY_SET.get(s, {})
    return [(n, m[n]) for n in m]


def cloth_id(set_name, name) -> int:
    s = set_name if set_name in SETS else DEFAULT_SET
    return int(CLOTHES_BY_SET[s].get(str(name), (0, 0))[0])


def cloth_name(value=None, set_name=None) -> str:
    """服装名（也接受服装层 ID：先按指定套找，再两套都找）"""
    if value is None or value == "":
        return ""
    s = set_name if set_name in SETS else None
    t = str(value).strip()
    if not t.isdigit():
        return t if _is_cloth_name(t) else ""
    cid = int(t)
    order = [s] if s else list(SETS)
    for ss in order:
        for n, (c, _h) in CLOTHES_BY_SET[ss].items():
            if c == cid:
                return n
    return ""


def _is_cloth_name(name) -> bool:
    return any(name in CLOTHES_BY_SET[s] for s in SETS)


def resolve_cloth(name) -> str:
    """口语 / AI 标记（[换装:制服]）→ 标准服装名；识别不出返回 "" """
    t = str(name or "").strip()
    if not t:
        return ""
    if _is_cloth_name(t):
        return t
    if t in CLOTH_ALIASES:
        return CLOTH_ALIASES[t]
    for k, v in CLOTH_ALIASES.items():
        if k in t:
            return v
    return ""


def common_cloths() -> list:
    """两套都有的服装名（用于桌宠"概率切换立绘类型"的灵动效果）"""
    return [n for n in CLOTH_ORDER
            if n in CLOTHES_BY_SET["a"] and n in CLOTHES_BY_SET["b"]]


# ══════════ 装扮读写 ══════════
def _decor_pairs(set_name: str) -> list:
    """该套的装饰 → [(层ID, 名字)]"""
    try:
        return [(int(i), str(n)) for n, i in DECORS_BY_SET[set_name].items()]
    except Exception:
        return []


def _decor_names(set_name: str, ids: list) -> set:
    """把某套的装饰层 ID 还原成名字集合"""
    m = {i: n for i, n in _decor_pairs(set_name)}
    out = set()
    for x in ids or []:
        try:
            n = m.get(int(x))
        except Exception:
            n = None
        if n:
            out.add(n)
    return out


def load_outfit(set_name=None) -> dict:
    """读取某套（默认 active）的装扮
    → {"set", "cloth"(名字), "cloth_id", "hair", "decor"[ids]}"""
    d = _raw_load()
    s = set_name if set_name in SETS else d["active"]
    ent = d.get(s) or _default_entry(s)
    name = ent.get("cloth") or DEFAULT_CLOTH
    if name not in CLOTHES_BY_SET[s]:
        name = DEFAULT_CLOTH
    cid, hair = CLOTHES_BY_SET[s][name]
    return {"set": s, "cloth": name, "cloth_id": int(cid), "hair": int(hair),
            "decor": [int(x) for x in (ent.get("decor") or [])]}


def save_outfit(cloth=None, hair=None, decor=None, set_name=None, make_active=False) -> bool:
    """保存装扮（写同一份配置，QQ 与桌宠共用）。
    cloth 可以是服装名，也可以是该套的服装层 ID；set_name 省略=当前 active 套。"""
    try:
        d = _raw_load()
        s = set_name if set_name in SETS else d["active"]
        cur = d.get(s) or _default_entry(s)
        name = cur.get("cloth") or DEFAULT_CLOTH
        if cloth is not None and cloth != "":
            nm = cloth_name(cloth, s) or resolve_cloth(cloth)
            if not nm or nm not in CLOTHES_BY_SET[s]:
                print(f"[PortraitOutfit] ⚠ 无法识别的服装: {cloth}")
                return False
            name = nm
        decors = cur.get("decor") or []
        if decor is not None:
            allowed = set(DECORS_BY_SET[s].values())
            decors = []
            for x in decor:
                try:
                    xi = int(x)
                except Exception:
                    continue
                if xi in allowed and xi not in decors:
                    decors.append(xi)
        d[s] = {"cloth": name, "decor": decors}
        # ★ 同步到另一套：按【服装名/装饰名】对应（a/b 的图层 ID 不同但名字相同）
        # 目的：切换立绘类型时衣服保持一致，不会变成另一件；
        #      也只有两套都有这件衣服时，自动切换才有意义（common_cloths 判定）。
        try:
            other = "b" if s == "a" else "a"
            names = _decor_names(s, decors)
            o_decors = [i for i, n in _decor_pairs(other) if n in names]
            d[other] = {"cloth": name, "decor": o_decors}
        except Exception as _e:
            print(f"[PortraitOutfit] ⚠ 同步两套装扮失败: {_e}")
        if make_active:
            d["active"] = s
        ok = _raw_save(d)
        if ok:
            print(f"[PortraitOutfit] 👗 {s} 套装扮已保存：{name}"
                  f"（装饰 {len(decors)}）{' · 已设为当前立绘类型' if make_active else ''}")
        return ok
    except Exception as e:
        print(f"[PortraitOutfit] ⚠ 保存装扮失败: {e}")
        return False


# ══════════ 图层处理 ══════════
def _index_path(set_name):
    """{fgimages}/{prefix}{set}.txt"""
    try:
        from pets.pet_registry import get_fgimages_dir, get_active_pet_id, get_pet_config
        d = get_fgimages_dir(get_active_pet_id())
        prefix = (get_pet_config(get_active_pet_id()).get("model") or {}).get("fgimages_prefix", "")
        if d:
            if prefix and os.path.exists(os.path.join(d, f"{prefix}{set_name}.txt")):
                return os.path.join(d, f"{prefix}{set_name}.txt")
            import glob
            hits = glob.glob(os.path.join(d, f"*{set_name}.txt"))
            if hits:
                return hits[0]
    except Exception:
        pass
    return ""


def _index_rows(set_name):
    """{layer_id: 名字}"""
    if set_name in _index_cache:
        return _index_cache[set_name]
    rows = {}
    try:
        p = _index_path(set_name)
        if p and os.path.exists(p):
            with open(p, encoding="utf-16") as f:
                for row in csv.reader(f, delimiter="\t"):
                    if len(row) > 9 and row[9].strip().isdigit():
                        rows[int(row[9])] = (row[1] or "").strip()
    except Exception as e:
        print(f"[PortraitOutfit] ⚠ 读取 {set_name} 套索引失败: {e}")
    _index_cache[set_name] = rows
    return rows


def _trans_table(src, dst):
    """{src 层 id → dst 层 id}：同名单映射 + 人工别名 + 服装/发型/装饰对应"""
    key = (src, dst)
    if key in _trans_cache:
        return _trans_cache[key]
    tbl = {}
    try:
        src_rows, dst_rows = _index_rows(src), _index_rows(dst)
        dst_by_name = {}
        for i, n in dst_rows.items():
            if n and n not in dst_by_name:
                dst_by_name[n] = i
        # 1) 同名
        for i, n in src_rows.items():
            if n and n in dst_by_name:
                tbl[i] = dst_by_name[n]
        # 2) 人工别名（仅 a→b 需要；反向自动生成）
        if src == "a" and dst == "b":
            for sn, dn in _EXPR_NAME_ALIAS.items():
                for i, n in src_rows.items():
                    if n == sn and dn in dst_by_name:
                        tbl[i] = dst_by_name[dn]
            tbl.update(_EXTRA_ID_MAP_A2B)
        elif src == "b" and dst == "a":
            for i, j in _EXTRA_ID_MAP_A2B.items():
                tbl.setdefault(j, i)
            for dn, sn in _EXPR_NAME_ALIAS.items():   # b 名 → a 名
                for i, n in src_rows.items():
                    if n == dn and sn in dst_by_name:
                        tbl[i] = dst_by_name[sn]
        # 3) 服装 / 发型 / 装饰（按名字/顺序对应）
        for n in CLOTH_ORDER:
            ca, ha = CLOTHES_BY_SET[src].get(n, (0, 0))
            cb, hb = CLOTHES_BY_SET[dst].get(n, (0, 0))
            if ca and cb:
                tbl[ca] = cb
                tbl[ha] = hb
        da, db = list(DECORS_BY_SET[src].values()), list(DECORS_BY_SET[dst].values())
        for k, v in enumerate(da):
            if k < len(db):
                tbl[v] = db[k]
        # 非刀服的常规发型最后写入（b 套只有一款头发，避免被刀服覆盖）
        tbl[CLOTHES_BY_SET[src]["制服"][1]] = CLOTHES_BY_SET[dst]["制服"][1]
    except Exception as e:
        print(f"[PortraitOutfit] ⚠ 建立 {src}→{dst} 图层映射失败: {e}")
    _trans_cache[key] = tbl
    return tbl


def detect_set(layers) -> str:
    """判断图层列表属于哪套立绘（两套 ID 空间互不重叠）"""
    try:
        ids = [int(x) for x in (layers or [])]
    except Exception:
        ids = []
    scores = {s: 0 for s in SETS}
    for s in SETS:
        known = _index_rows(s).keys()
        for i in ids:
            if i in known:
                scores[s] += 1
    best = max(scores, key=lambda s: scores[s])
    return best if scores[best] else ""


def translate_layers(layers, src_set, dst_set) -> list:
    """把某套的图层列表换算成另一套的图层列表（服装/发型/装饰/表情）"""
    if not src_set or not dst_set or src_set == dst_set:
        return list(layers or [])
    tbl = _trans_table(src_set, dst_set)
    known = _index_rows(src_set)
    fb = EXPR_FALLBACK.get(dst_set)
    out = []
    for x in (layers or []):
        try:
            i = int(x)
        except Exception:
            continue
        j = tbl.get(i)
        if j is None:
            if i in known:
                j = fb                 # 表情找不到对应 → 用该套基准脸
            else:
                continue               # 该套根本不存在的图层 → 丢弃
        if j and j not in out:
            out.append(j)
    return out


def normalize_layers(layers, set_name):
    """确保图层列表属于指定套（跨套自动翻译；已是该套则原样返回）"""
    try:
        cur = detect_set(layers)
        if cur and set_name and cur != set_name:
            print(f"[PortraitOutfit] 🔄 图层 {cur} 套 → {set_name} 套（跨套翻译）")
            return translate_layers(layers, cur, set_name)
    except Exception:
        pass
    return list(layers or [])


def apply_outfit(layers, set_name=None, outfit=None):
    """把图层列表里的身体层/发型层替换为该套当前装扮（桌宠 2D 立绘用）。
    没有身体层时在首位补一个，保证换装一定生效。"""
    try:
        of = dict(outfit) if outfit else None
        if not of:
            s_hint = set_name or detect_set(layers) or active_set()
            of = load_outfit(s_hint)
        s = of.get("set") or DEFAULT_SET
        if set_name in SETS and set_name != s:
            of = load_outfit(set_name)
            s = set_name
        cloth = int(of.get("cloth_id") or CLOTHES_BY_SET[s][DEFAULT_CLOTH][0])
        hair = int(of.get("hair") or CLOTHES_BY_SET[s][DEFAULT_CLOTH][1])
        body = BODY_LAYERS_BY_SET.get(s, set())
        hairs = HAIR_LAYERS_BY_SET.get(s, set())
        out = []
        replaced = False
        for lid in (layers or []):
            try:
                li = int(lid)
            except Exception:
                continue
            if li in body:
                out.append(cloth)
                replaced = True
            elif li in hairs:
                out.append(hair)
            else:
                out.append(li)
        for d in (of.get("decor") or []):
            if d not in out:
                out.append(int(d))
        if not replaced:
            out.insert(0, cloth)
        return out
    except Exception as e:
        print(f"[PortraitOutfit] ⚠ 应用装扮失败: {e}")
        return list(layers or [])
