import csv
import os
import re

import cv2
import numpy as np

from pets.pet_registry import get_fgimages_dir, get_active_pet_id, get_pet_config

'''
传入一个列表最多可以有4个参数
'''

# ══════════════════ 图层位置微调（防穿模）══════════════════
# pet.json: model.layer_adjust = {"a": {"cloth": [dx,dy,scale], "expr": [...], ...}}
# 类别：base 基础人物 / expr 表情 / hair 头发 / cloth 服装 / decor 装饰
LAYER_CATS = ("base", "expr", "hair", "cloth", "decor")
_CAT_LABEL = {"base": "基础人物", "expr": "表情", "hair": "头发",
              "cloth": "服装", "decor": "装饰"}


def _adjust_table(pet_id: str, set_name: str) -> dict:
    """取某套的图层微调表（环境变量 AIPET_LAYER_ADJUST 可临时覆盖，供界面预览）"""
    out = {}
    try:
        import json as _json
        env = os.environ.get("AIPET_LAYER_ADJUST")
        if env:
            d = _json.loads(env)
            out = (d.get(set_name) or d) if isinstance(d, dict) else {}
        else:
            cfg = get_pet_config(pet_id)
            d = ((cfg.get("model") or {}).get("layer_adjust") or {})
            out = d.get(set_name) or d.get("a") or {}
    except Exception:
        out = {}
    res = {}
    for k, v in (out or {}).items():
        if k not in LAYER_CATS:
            continue
        try:
            dx = int(v[0]) if len(v) > 0 else 0
            dy = int(v[1]) if len(v) > 1 else 0
            sc = float(v[2]) if len(v) > 2 and v[2] else 1.0
            if dx or dy or abs(sc - 1.0) > 0.001:
                res[k] = (dx, dy, max(0.3, min(2.0, sc)))
        except Exception:
            continue
    return res


def _category_of(layer_id, set_name: str, pet_id: str) -> str:
    """判断某图层属于哪一类（用于套用对应的微调）"""
    try:
        lid = int(layer_id)
    except Exception:
        return "base"
    s = str(set_name or "a")
    # 表情：新角色用 portrait.emotions，老角色用内置情绪表
    try:
        from pets.pet_registry import get_portrait_emotions
        if lid in set(get_portrait_emotions(pet_id).values()):
            return "expr"
    except Exception:
        pass
    try:
        from qq.qq_portrait import EMOTION_MAP
        if lid in {v[0] for v in EMOTION_MAP.values() if v}:
            return "expr"
    except Exception:
        pass
    try:
        from tool.portrait_outfit import CLOTHES_BY_SET, DECORS_BY_SET
        tbl = CLOTHES_BY_SET.get(s) or {}
        if any(lid in (v[0], v[1]) for v in tbl.values()):
            # 同一件服装的「身体层」和「发型层」分开算
            body = {v[0] for v in tbl.values()}
            return "cloth" if lid in body else "hair"
        if lid in set((DECORS_BY_SET.get(s) or {}).values()):
            return "decor"
    except Exception:
        pass
    return "base"


def generate_fgimage(target, embeddings_layers, pet_id: str = None):
    pet_id = pet_id or get_active_pet_id()
    fg_dir = get_fgimages_dir(pet_id)
    if not fg_dir:
        print(f"[generate] ⚠ 桌宠 [{pet_id}] 无 fgimages 目录，返回空画布")
        return np.zeros((1, 1, 4), dtype=np.uint8)

    cfg = get_pet_config(pet_id)
    # 前缀解析：model.fgimages_prefix → portrait.prefix → 角色ID（空则回退ムラサメ）
    # ⚠ 绝不返回空：老版本新建的角色前缀留空时，这里会退回「ムラサメ」去合成，
    #   索引不存在 → 启动异常 → 桌宠窗口都不出现。
    try:
        from pets.pet_registry import get_fgimages_prefix
        prefix = get_fgimages_prefix(pet_id)
    except Exception:
        prefix = cfg.get("model", {}).get("fgimages_prefix", "")
    if prefix and prefix not in target:
        # 兼容传入前缀（如 "ムラサメa"）或仅套装名（如 "a"）
        target = f"{prefix}{target}"
    idx_path = os.path.join(fg_dir, f"{target}.txt")
    if not os.path.isfile(idx_path):
        # 不再 assert 崩掉整个桌宠：给出明确日志 + 空画布（桌宠照常启动、只是暂无立绘）
        _alts = [f for f in os.listdir(fg_dir) if f.endswith(".txt")]
        print(f"[generate] ⚠ 未找到图层索引: {target}.txt（目录里现有: {_alts}）"
              f"\n           角色 [{pet_id}] 的立绘前缀 = {prefix!r}，"
              f"可用「立绘工坊」或「桌宠设置」检查立绘素材。")
        return np.zeros((1, 1, 4), dtype=np.uint8)

    # ===== 防御：云端 AI 返回格式千奇百怪 → 统一展平为「图层 ID 列表」=====
    # 正常：  [1715, 1475, 1719, 1261]            （int 列表）
    # 畸形1： 1715                                （裸 int）
    # 畸形2： "1715, 1731, 1719, 1261"            （字符串数组整体）
    # 畸形3： ['1715, 1731, 1719, 1261']          （list 里只有 1 个字符串包含全部 ID）
    # 畸形4： "['1715', '1731', '1719', '1261']"  （字符串里嵌套列表）
    # 上述全部通过正则提取数字，展平成独立 int 图层 ID。
    def _flatten_layers(layers):
        result = []
        if isinstance(layers, (int, float)):
            result.append(int(layers))
            return result
        if isinstance(layers, str):
            # 提取字符串中所有数字（如 "1715, 1731, 1719, 1261" → [1715,1731,1719,1261]）
            nums = re.findall(r"\d+", layers)
            result.extend(int(n) for n in nums)
            return result
        if isinstance(layers, (list, tuple)):
            for item in layers:
                result.extend(_flatten_layers(item))
            return result
        return result

    embeddings_layers = _flatten_layers(embeddings_layers)
    if not embeddings_layers:
        print(f"[generate] ⚠ embeddings_layers 无效（无任何数字），返回空画布")
        return np.zeros((1, 1, 4), dtype=np.uint8)

    with open(os.path.join(fg_dir, f"{target}.txt"), encoding='utf-16 le') as cf:
        infos = list(csv.reader(cf, delimiter='\t'))

    # ⚠ 这里原来写死了丛雨索引的行区间（ムラサメa → infos[57:65]，其它 → infos[47:51]）。
    #   那些行给的是"站立位置"基准，对别的角色/别的图层集合会**大于**所选图层 →
    #   算出来的偏移为负 → 人物被裁掉一大块（实测：b 套左边裁 365/1016px、上边 282px；
    #   a 套 453/1156px、197px）—— 这正是反复反馈的「立绘只显示了一半」。
    #   现在画布原点只按**所选图层**求（见下面的 base_x/base_y），不再依赖任何写死的行号。

    # ===== 关键修复：图层文件存在性过滤（AI 偶发跨服装返回不存在的 ID → 跳过不崩）=====
    # 例：A 立绘模式 AI 返回 B 套 ID(如 1475 撒娇) → A 套素材没有该文件 →
    # 若不过滤，cv2.imdecode 读缺失文件直接 FileNotFoundError 崩溃。
    valid_layers = []
    for name in embeddings_layers:
        img_file = os.path.join(fg_dir, f"{target}_{name}.png")
        if os.path.exists(img_file):
            valid_layers.append(name)
        else:
            print(f"[generate] ⚠ 跳过缺失图层: {target}_{name}.png（AI 跨服装/越界返回了不存在的 ID）")
    # ===== 兜底（一）：所有图层都缺 → 单图模式退回角色默认表情整图 =====
    # ⚠ 必须放在「所有图层均缺失就返回空画布」之前：single 模式（每个表情一张整图）
    #   的角色，AI 很容易返回别的角色（丛雨）的图层 ID → 全缺 → 桌宠就变成空白/1x1 窗。
    if not valid_layers:
        try:
            from pets.pet_registry import get_portrait_default_layers
            _dflt = [ly for ly in get_portrait_default_layers(pet_id)
                     if os.path.exists(os.path.join(fg_dir, f"{target}_{ly}.png"))]
        except Exception:
            _dflt = []
        if _dflt:
            print(f"[generate] ℹ 返回的图层 {embeddings_layers} 本角色都没有 → 改用默认表情图 {_dflt}")
            valid_layers = _dflt
        else:
            print(f"[generate] ⚠ 所有图层均缺失，返回空画布")
            return np.zeros((1, 1, 4), dtype=np.uint8)

    # ★ 图层与坐标必须**一一对应**：按索引里的图层号建表，再按 valid_layers 的顺序取。
    #   老写法是"遍历 infos 找匹配"，某个图层在索引里查不到时 all_positions 会比 valid_layers
    #   短 → 后面 `valid_layers[idx]` 张冠李戴，身体图被贴到表情的坐标上 → 只画出一小块。
    _pos_of = {}
    for _x in infos:
        if len(_x) > 9:
            try:
                _pos_of[str(_x[9])] = (int(_x[2]), int(_x[3]), int(_x[4]), int(_x[5]))
            except (ValueError, IndexError):
                pass
    _pairs = [(n, _pos_of.get(str(n))) for n in valid_layers]
    _lost = [n for n, _p in _pairs if _p is None]
    if _lost:
        print(f"[generate] ⚠ 图层 {_lost} 不在 {target}.txt 索引里 → 跳过（避免贴错位置）")
    valid_layers = [n for n, _p in _pairs if _p is not None]
    all_positions = [_p for _n, _p in _pairs if _p is not None]

    # ===== 兜底（一·五）：图层里没有「表情」→ 补上该角色默认表情 =====
    # （AI 有时只返回服装/头发，结果就是「只有衣服没有脸」）
    try:
        _is2d = str(get_pet_config(pet_id).get("portrait", {}).get("mode") or "layers") == "layers"
    except Exception:
        _is2d = False
    if _is2d:
        try:
            _has_expr = any(_category_of(l, str(target)[-1:] or "a", pet_id) == "expr"
                            for l in valid_layers)
            if not _has_expr:
                _emo_ids = set()
                try:
                    from qq.qq_portrait import EMOTION_MAP
                    _emo_ids = {v[0] for v in EMOTION_MAP.values() if v}
                except Exception:
                    pass
                _dflt = EMOTION_MAP.get("平静", (1292, None))[0] if _emo_ids else None
                if _dflt and os.path.exists(os.path.join(fg_dir, f"{target}_{_dflt}.png")):
                    print(f"[generate] ℹ 图层里没有表情 → 补默认表情 {_dflt}")
                    if str(_dflt) in _pos_of:
                        valid_layers.append(_dflt)
                        all_positions.append(_pos_of[str(_dflt)])
                    else:
                        print(f"[generate] ⚠ 默认表情 {_dflt} 不在索引里 → 不补（否则会贴错位置）")
        except Exception as _e:
            print(f"[generate] ⚠ 补表情失败: {_e}")

    # ===== 兜底（二）：图层 ID 在索引文件里找不到 → 同样退回默认表情整图 =====
    if not all_positions:
        try:
            from pets.pet_registry import get_portrait_default_layers
            _dflt = [ly for ly in get_portrait_default_layers(pet_id)
                     if os.path.exists(os.path.join(fg_dir, f"{target}_{ly}.png"))]
        except Exception:
            _dflt = []
        if _dflt:
            _p2 = [(n, _pos_of.get(str(n))) for n in _dflt]
            _d2 = [n for n, _p in _p2 if _p is None]
            if _d2:
                print(f"[generate] ⚠ 默认表情 {_d2} 不在索引里 → 跳过")
            valid_layers = [n for n, _p in _p2 if _p is not None]
            all_positions = [_p for _n, _p in _p2 if _p is not None]
            if valid_layers:
                print(f"[generate] ℹ 图层不在本角色索引中 → 改用默认表情图 {valid_layers}")
        if not all_positions:
            print(f"[generate] ⚠ 图层 ID {valid_layers} 在 {target}.txt 中未匹配到，返回空画布")
            return np.zeros((1, 1, 4), dtype=np.uint8)

    # 画布原点 = **所有要画的图层**的左上角最小者。
    # ⚠ 绝不能让"基准行"反超所选图层（那会把偏移变成负数 → 人物被裁，见文件上方说明）；
    #   也不能用"索引里全部行"兜底 —— 那同样可能反超（别的角色索引行长得多）。
    base_x = min((p[0] for p in all_positions), default=0)
    base_y = min((p[1] for p in all_positions), default=0)

    all_positions = [(pos[0] - base_x, pos[1] - base_y, pos[2], pos[3])
                     for pos in all_positions]

    # 画布 = 所选图层的包围盒（与旧版本完全一致的几何：不因微调而偏移/放大）
    _adj = _adjust_table(pet_id, str(target)[-1:] if str(target)[-1:] in ("a", "b") else "a")
    canvas_scale = (max([(x[0] + x[2]) for x in all_positions]),
                    max([(x[1] + x[3]) for x in all_positions]))

    canvas = np.zeros((canvas_scale[1], canvas_scale[0], 4), dtype=np.uint8)

    for idx, pos in enumerate(all_positions):
        path = os.path.join(fg_dir, f"{target}_{valid_layers[idx]}.png")
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)
        if image is not None:
            _dx = _dy = 0
            _sc = 1.0
            if _adj:
                _cat = _category_of(valid_layers[idx], str(target)[-1:] or "a", pet_id)
                if _cat in _adj:
                    _dx, _dy, _sc = _adj[_cat]
            if abs(_sc - 1.0) > 0.001:
                _h0, _w0 = image.shape[:2]
                _nw, _nh = max(1, int(_w0 * _sc)), max(1, int(_h0 * _sc))
                image = cv2.resize(image, (_nw, _nh), interpolation=cv2.INTER_LINEAR)
                _dx += int((_w0 - _nw) / 2)
                _dy += int((_h0 - _nh) / 2)
            x_offset = pos[0] + _dx
            y_offset = pos[1] + _dy
            h, w = image.shape[:2]
            # ★ 图比画布大（索引里宽高写小了、或微调放大过）→ **画布就地长大**，绝不裁人物。
            _ch, _cw = canvas.shape[0], canvas.shape[1]
            if (x_offset >= 0 and y_offset >= 0
                    and (x_offset + w > _cw or y_offset + h > _ch)):
                _nw, _nh = max(_cw, x_offset + w), max(_ch, y_offset + h)
                _big = np.zeros((_nh, _nw, 4), dtype=np.uint8)
                _big[:_ch, :_cw] = canvas
                canvas = _big
                _ch, _cw = _nh, _nw
            # 偏移为负（微调把它推到画布外）→ 这种情况只能裁，避免广播报错
            if x_offset < 0 or y_offset < 0 or x_offset + w > _cw or y_offset + h > _ch:
                _x0, _y0 = max(0, x_offset), max(0, y_offset)
                _x1, _y1 = min(_cw, x_offset + w), min(_ch, y_offset + h)
                if _x1 <= _x0 or _y1 <= _y0:
                    continue
                _sx, _sy = _x0 - x_offset, _y0 - y_offset
                image = image[_sy:_sy + (_y1 - _y0), _sx:_sx + (_x1 - _x0)]
                x_offset, y_offset = _x0, _y0
                h, w = image.shape[:2]
            alpha_img = image[..., 3:] / 255.0
            alpha_canvas = 1.0 - alpha_img
            for c in range(3):
                canvas[y_offset:y_offset + h, x_offset:x_offset + w, c] = (
                    alpha_img[..., 0] * image[..., c] +
                    alpha_canvas[..., 0] * canvas[y_offset:y_offset +
                                                  h, x_offset:x_offset + w, c]
                )
            canvas[y_offset:y_offset + h, x_offset:x_offset + w, 3] = (
                np.maximum(
                    image[..., 3], canvas[y_offset:y_offset + h, x_offset:x_offset + w, 3])
            )

    return canvas
