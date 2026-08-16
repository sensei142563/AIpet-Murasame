"""人脸识别引擎 — CNN 编码 + 数据增强 + 相似度评估（待训练完成后启用）

使用 face_recognition 库的 128 维 CNN 编码替代纯哈希比对。
当前状态：占位代码，等待 dlib/face_recognition 安装完毕后方可激活。

激活步骤：
1. 安装依赖：pip install dlib face_recognition
2. 在所有调用处将 import 从 tool.face_recognition 改为 tool.face_recognition_cnn
3. 删除 face_shibie/cache/ 下的旧缓存，重启桌宠自动生成 CNN 编码库

架构：
1. 注册阶段：对每张参考照片做数据增强 + CNN 编码 → 128维 templates 库
2. 识别阶段：摄像头帧 → HOG 检测人脸 → CNN 编码 → 与 templates 比欧氏距离
3. 决策：master ≥0.55 且 ≥others → 主人；others ≥0.55 且 >master → 他人
"""
import os
import json
import base64
import shutil
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ============ 路径配置 ============
FACE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "face_shibie")
FACES_JSON = os.path.join(FACE_DIR, "faces.json")
MASTER_DIR = os.path.join(FACE_DIR, "master")
OTHERS_DIR = os.path.join(FACE_DIR, "others")
CACHE_DIR = os.path.join(FACE_DIR, "cache")
MASTER_ENCODINGS_CACHE = os.path.join(CACHE_DIR, "cnn_master_encodings.npy")
OTHERS_ENCODINGS_CACHE = os.path.join(CACHE_DIR, "cnn_others_encodings.npy")

os.makedirs(MASTER_DIR, exist_ok=True)
os.makedirs(OTHERS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ============ 延迟导入 face_recognition（避免启动时崩溃） ============
_face_recognition_available = False
try:
    import face_recognition
    _face_recognition_available = True
    print("[Face-CNN] face_recognition 已就绪")
except ImportError:
    print("[Face-CNN] face_recognition 未安装，请执行 pip install dlib face_recognition")


# ============ 数据增强 ============
def augment_image(img: np.ndarray, rotations: int = 5, brightness_factors: int = 3) -> List[np.ndarray]:
    augmented = []
    rows, cols = img.shape[:2]
    bf_values = np.linspace(0.7, 1.4, brightness_factors)
    angle_values = np.linspace(-15, 15, rotations)
    for bf in bf_values:
        bright = cv2.convertScaleAbs(img, alpha=bf, beta=0)
        augmented.append(bright)
        for ang in angle_values:
            M = cv2.getRotationMatrix2D((cols / 2, rows / 2), ang, 1.0)
            rot = cv2.warpAffine(bright, M, (cols, rows))
            augmented.append(rot)
    return augmented


# ============ 文件 IO ============
def imread_chinese(path: str) -> np.ndarray:
    if not os.path.exists(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_chinese(path: str, img: np.ndarray, ext: str = ".jpg"):
    cv2.imencode(ext, img)[1].tofile(path)


# ============ CNN 编码计算 ============
def compute_face_encodings(image_path: str, num_jitters: int = 2) -> List[np.ndarray]:
    """从单张照片提取人脸 CNN 编码（128维向量）"""
    if not _face_recognition_available:
        return []
    img = imread_chinese(image_path)
    if img is None:
        return []
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb)
    if locs:
        encs = face_recognition.face_encodings(rgb, known_face_locations=locs,
                                                num_jitters=num_jitters)
    else:
        encs = face_recognition.face_encodings(rgb, num_jitters=num_jitters)
    return encs


# ============ 编码库构建 ============
def _compute_master_encodings(cfg: dict) -> np.ndarray:
    if os.path.exists(MASTER_ENCODINGS_CACHE):
        return np.load(MASTER_ENCODINGS_CACHE, allow_pickle=True)

    all_encs = []
    for item in cfg.get("master", []):
        img_path = os.path.normpath(os.path.join(FACE_DIR,
                                                  item["file"].replace("/", os.sep)))
        encs = compute_face_encodings(img_path, num_jitters=1)
        if encs:
            all_encs.extend(encs)
        img = imread_chinese(img_path)
        if img is not None:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            for aug in augment_image(rgb):
                locs = face_recognition.face_locations(aug) if _face_recognition_available else []
                if locs:
                    aug_encs = face_recognition.face_encodings(
                        aug, known_face_locations=locs, num_jitters=1)
                    all_encs.extend(aug_encs)

    result = np.array(all_encs) if all_encs else np.array([])
    np.save(MASTER_ENCODINGS_CACHE, result)
    print(f"[Face-CNN] 主人编码: {len(result)} 个向量")
    return result


def _compute_others_encodings(cfg: dict) -> Dict[str, Tuple[np.ndarray, str]]:
    if os.path.exists(OTHERS_ENCODINGS_CACHE):
        return np.load(OTHERS_ENCODINGS_CACHE, allow_pickle=True).item()

    result = {}
    for name, val in cfg.get("others", {}).items():
        if isinstance(val, dict):
            file_path = val.get("file", "")
            relation = val.get("relation", "")
        else:
            file_path = val
            relation = ""
        img_path = os.path.normpath(os.path.join(FACE_DIR,
                                                  file_path.replace("/", os.sep)))
        encs = compute_face_encodings(img_path, num_jitters=1)
        if encs:
            img = imread_chinese(img_path)
            if img is not None:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                for aug in augment_image(rgb):
                    locs = face_recognition.face_locations(aug) if _face_recognition_available else []
                    if locs:
                        aug_encs = face_recognition.face_encodings(
                            aug, known_face_locations=locs, num_jitters=1)
                        encs.extend(aug_encs)
        if encs:
            result[name] = (np.array(encs), relation)

    np.save(OTHERS_ENCODINGS_CACHE, result)
    return result


# ============ 注册中心 ============
def _load_faces_config() -> dict:
    if not os.path.exists(FACES_JSON):
        return {"master": [], "others": {}}
    with open(FACES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_faces_config(cfg: dict):
    with open(FACES_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ============ 人脸检测和识别 ============
def detect_faces(frame: np.ndarray) -> list:
    if not _face_recognition_available:
        return []
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb)
    return [(x, y, x2 - x, y2 - y) for (y, x2, y2, x) in locs]


def recognize_face(face_img: np.ndarray) -> dict:
    if not _face_recognition_available:
        return {"name": "unknown", "is_master": False, "confidence": 0.0, "relation": ""}

    rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
    encs = face_recognition.face_encodings(rgb)
    if not encs:
        return {"name": "unknown", "is_master": False, "confidence": 0.0, "relation": ""}
    query_enc = encs[0]

    # 1. 与主人模板比对
    master_encs = _get_master_encodings()
    if len(master_encs) > 0:
        distances = face_recognition.face_distance(master_encs, query_enc)
        best_master_dist = distances.min()
    else:
        best_master_dist = 1.0
    master_conf = round(max(0, 1 - best_master_dist), 3)

    # 2. 与其他人模板比对
    others_info = _get_others_encodings()
    best_other_name, best_other_dist, best_other_rel = None, 1.0, ""
    for name, (encs_arr, rel) in others_info.items():
        if len(encs_arr) == 0:
            continue
        distances = face_recognition.face_distance(encs_arr, query_enc)
        idx = np.argmin(distances)
        if distances[idx] < best_other_dist:
            best_other_dist = distances[idx]
            best_other_name = name
            best_other_rel = rel
    other_conf = round(max(0, 1 - best_other_dist), 3)

    # 3. 互斥判断
    if best_other_name and best_other_dist < 0.55 and (len(master_encs) == 0 or
                                                        best_other_dist < best_master_dist):
        return {"name": best_other_name, "is_master": False,
                "confidence": other_conf, "relation": best_other_rel}
    if len(master_encs) > 0 and best_master_dist < 0.55:
        return {"name": "主人", "is_master": True,
                "confidence": master_conf, "relation": ""}
    return {"name": "unknown", "is_master": False,
            "confidence": max(master_conf, other_conf), "relation": ""}


def _get_master_encodings() -> np.ndarray:
    if os.path.exists(MASTER_ENCODINGS_CACHE):
        return np.load(MASTER_ENCODINGS_CACHE, allow_pickle=True)
    cfg = _load_faces_config()
    return _compute_master_encodings(cfg)


def _get_others_encodings() -> Dict:
    if os.path.exists(OTHERS_ENCODINGS_CACHE):
        return np.load(OTHERS_ENCODINGS_CACHE, allow_pickle=True).item()
    cfg = _load_faces_config()
    return _compute_others_encodings(cfg)


def recognize_faces_in_frame(frame: np.ndarray) -> list:
    lst = detect_faces(frame)
    results = []
    for (x, y, w, h) in lst:
        x2 = min(frame.shape[1], x + max(1, w))
        y2 = min(frame.shape[0], y + max(1, h))
        roi = frame[y:y2, x:x2]
        if roi.size == 0:
            continue
        rec = recognize_face(roi)
        rec["location"] = (x, y, w, h)
        results.append(rec)
    return results


def recognize_from_base64(img_b64: str) -> list:
    if img_b64.startswith("data:"):
        img_b64 = img_b64.split(",")[-1]
    nparr = np.frombuffer(base64.b64decode(img_b64), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return []
    return recognize_faces_in_frame(frame)


# ============ 人脸管理 ============
def add_master_face(image_path: str, desc: str = "") -> bool:
    cfg = _load_faces_config()
    ext = os.path.splitext(image_path)[1] or ".jpg"
    idx = len(cfg.get("master", [])) + 1
    new_name = f"{idx:03d}{ext}"
    new_path = os.path.join(MASTER_DIR, new_name)
    img = imread_chinese(image_path)
    if img is None:
        return False
    imwrite_chinese(new_path, img, ext)
    cfg.setdefault("master", []).append(
        {"file": f"master/{new_name}", "desc": desc or f"第{idx}张主人照"})
    _save_faces_config(cfg)
    clear_cache()
    return True


def add_other_face(image_path: str, name: str, relation: str = "") -> bool:
    cfg = _load_faces_config()
    if name in cfg.get("others", {}):
        return False
    ext = os.path.splitext(image_path)[1] or ".jpg"
    new_name = f"{name}{ext}"
    new_path = os.path.join(OTHERS_DIR, new_name)
    img = imread_chinese(image_path)
    if img is None:
        return False
    imwrite_chinese(new_path, img, ext)
    cfg.setdefault("others", {})[name] = {"file": f"others/{new_name}",
                                           "relation": relation or ""}
    _save_faces_config(cfg)
    clear_cache()
    return True


def delete_face(name: str) -> bool:
    cfg = _load_faces_config()
    if name == "主人":
        cfg["master"] = []
        for f in os.listdir(MASTER_DIR):
            os.remove(os.path.join(MASTER_DIR, f))
    elif name in cfg.get("others", {}):
        val = cfg["others"][name]
        fp = val.get("file", "") if isinstance(val, dict) else val
        full = os.path.join(FACE_DIR, fp)
        if os.path.exists(full):
            os.remove(full)
        del cfg["others"][name]
    else:
        return False
    _save_faces_config(cfg)
    clear_cache()
    return True


def clear_cache():
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR):
            os.remove(os.path.join(CACHE_DIR, f))


def reload_known_faces():
    clear_cache()
    cfg = _load_faces_config()
    _compute_master_encodings(cfg)
    _compute_others_encodings(cfg)


def get_all_known_faces():
    return {}, {}