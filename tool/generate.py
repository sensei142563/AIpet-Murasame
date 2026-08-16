import csv
import os
import re

import cv2
import numpy as np

from pets.pet_registry import get_fgimages_dir, get_active_pet_id, get_pet_config

'''
传入一个列表最多可以有4个参数
'''
def generate_fgimage(target, embeddings_layers, pet_id: str = None):
    pet_id = pet_id or get_active_pet_id()
    fg_dir = get_fgimages_dir(pet_id)
    if not fg_dir:
        print(f"[generate] ⚠ 桌宠 [{pet_id}] 无 fgimages 目录，返回空画布")
        return np.zeros((1, 1, 4), dtype=np.uint8)

    cfg = get_pet_config(pet_id)
    prefix = cfg.get("model", {}).get("fgimages_prefix", "")
    if prefix:
        # 兼容传入前缀（如 "ムラサメa"）或仅套装名（如 "a"）
        if prefix not in target:
            target = f"{prefix}{target}"
    assert os.path.isfile(os.path.join(fg_dir, f"{target}.txt")), f"未找到图层索引: {target}.txt"

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

    if target == "ムラサメa":
        all_base = infos[57:65]
    else:
        all_base = infos[47:51]

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
    if not valid_layers:
        print(f"[generate] ⚠ 所有图层均缺失，返回空画布")
        return np.zeros((1, 1, 4), dtype=np.uint8)

    all_positions = [(int(x[2]), int(x[3]), int(x[4]), int(x[5]))
                     for name in valid_layers for x in infos if x[9] == str(name)]
    all_base = [(int(x[2]), int(x[3]), int(x[4]), int(x[5]))
                for x in all_base]

    # ===== 兜底：图层 ID 在索引文件中找不到 → all_positions 为空 → 返回空画布不崩 =====
    if not all_positions:
        print(f"[generate] ⚠ 图层 ID {valid_layers} 在 {target}.txt 中未匹配到，返回空画布")
        return np.zeros((1, 1, 4), dtype=np.uint8)

    all_positions = [(pos[0] - min(pos[0] for pos in all_base), pos[1] - min(pos[1] for pos in all_base), pos[2], pos[3])
                     for pos in all_positions]

    canvas_scale = (max([(x[0] + x[2]) for x in all_positions]),
                    max([(x[1] + x[3]) for x in all_positions]))

    canvas = np.zeros((canvas_scale[1], canvas_scale[0], 4), dtype=np.uint8)

    for idx, pos in enumerate(all_positions):
        path = os.path.join(fg_dir, f"{target}_{valid_layers[idx]}.png")
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)
        if image is not None:
            x_offset = pos[0]
            y_offset = pos[1]
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
