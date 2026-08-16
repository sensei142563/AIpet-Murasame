"""人脸识别引擎 — ArcFace ONNX (512维 embedding + 余弦相似度)

依赖：pip install insightface opencv-python numpy
纯 onnxruntime 推理，无需 dlib/CMake/CUDA。

架构：
1. 注册阶段：对每张参考照片做 ArcFace 512维 embedding → 模板库
2. 识别阶段：摄像头帧 → Haar 人脸检测 → ArcFace embedding → 余弦相似度比对
3. 决策：master 最大余弦相似度 ≥ 0.35 → 主人；others 最大 ≥ 0.40 → 他人
"""
import os
import json
import base64
import sys as _sys
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from tool.paths import app_base_dir, data_path

# ============ 识别阈值（余弦相似度，0~1，越大越相似） ============
MASTER_SIM = 0.28     # 主人：max 余弦相似度 ≥ 此值才认（ArcFace 余弦相似度阈值）
OTHER_SIM = 0.35      # 他人：max 余弦相似度 ≥ 此值才认
# 互斥策略：主人优先 — 只在他人的相似度明显高于主人时才匹配他人
# 因为主人模板多 → 余弦相似度分布更宽，需要给他人更高的门槛

# ============ 人脸检测 ============
_face_cascade = None

def _get_cascade():
    global _face_cascade
    if _face_cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(cascade_path)
    return _face_cascade

# ============ ArcFace 推理引擎（ONNX Runtime） ============
_arcface_model = None
_arcface_input_size = (112, 112)

def _load_arcface():
    global _arcface_model
    if _arcface_model is not None:
        return True

    try:
        import insightface
        # 自动下载并使用 buffalo_l 模型包中的 w600k_r50
        _arcface_model = insightface.model_zoo.get_model('buffalo_l')
        if _arcface_model is None:
            print("[Face] ArcFace 模型返回 None，检查 ~/.insightface/models/buffalo_l/")
            return False
        print(f"[Face] ArcFace ONNX 模型已加载（512维）")
        return True
    except Exception as e:
        print(f"[Face] ArcFace 模型加载失败: {e}")
        print("[Face] 回退到三哈希引擎")
        return False

def _af_embedding(face_img: np.ndarray) -> Optional[np.ndarray]:
    """ArcFace 512维 embedding，输入任意尺寸人脸区域"""
    if not _load_arcface():
        return None
    try:
        # ArcFace 需要 112x112 RGB 输入
        resized = cv2.resize(face_img, (112, 112))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        emb = _arcface_model.get_feat(rgb)
        if emb is not None:
            emb = np.asarray(emb, dtype=np.float32).flatten()
            if len(emb) == 512:
                return emb
        return None
    except Exception as e:
        print(f"[Face] ArcFace embedding 失败: {e}")
        return None

# ============ 三哈希回退引擎 ============
HASH_SIZE = 32

def _dhash(img, size=HASH_SIZE):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    resized = cv2.resize(gray, (size+1, size))
    return (resized[:, 1:] > resized[:, :-1]).flatten()

def _ahash(img, size=HASH_SIZE):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    resized = cv2.resize(gray, (size, size))
    return (resized > resized.mean()).flatten()

def _phash(img, size=HASH_SIZE):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    resized = cv2.resize(gray, (size*2, size*2))
    dct = cv2.dct(np.float32(resized))
    dct_low = dct[:size, :size]
    return (dct_low > dct_low.mean()).flatten()

def _triple_hash(img):
    return np.concatenate([_dhash(img), _ahash(img), _phash(img)])

def _hamming(h1, h2):
    return np.sum(h1 != h2) / len(h1) if len(h1) == len(h2) else 1.0

_drop_hash = False  # 标记是否跳过三哈希模板构建

# ============ 路径配置（统一走公共基准，exe 模式 → exe 旁；源码 → 项目根）============
FACE_DIR = data_path("face_shibie")
FACES_JSON = os.path.join(FACE_DIR, "faces.json")
MASTER_DIR = os.path.join(FACE_DIR, "master")
OTHERS_DIR = os.path.join(FACE_DIR, "others")
CACHE_DIR = os.path.join(FACE_DIR, "cache")
MASTER_EMB_CACHE = os.path.join(CACHE_DIR, "master_emb.npy")
OTHERS_EMB_CACHE = os.path.join(CACHE_DIR, "others_emb.npy")

os.makedirs(MASTER_DIR, exist_ok=True)
os.makedirs(OTHERS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ============ 文件 IO ============
def _imread(path):
    if not os.path.exists(path): return None
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

def _imwrite(path, img, ext=".jpg"):
    cv2.imencode(ext, img)[1].tofile(path)

# ============ 人脸检测 ============
_clahe = None

def _get_clahe():
    global _clahe
    if _clahe is None:
        _clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return _clahe

def detect_faces(frame: np.ndarray) -> list:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    equalized = _get_clahe().apply(gray)
    cascade = _get_cascade()
    faces = cascade.detectMultiScale(equalized, 1.1, 3, minSize=(40,40))
    faces = [(int(x), int(y), int(w), int(h)) for (x,y,w,h) in faces]
    if not faces:
        faces = cascade.detectMultiScale(equalized, 1.05, 2, minSize=(30,30))
        faces = [(int(x), int(y), int(w), int(h)) for (x,y,w,h) in faces]
    return faces

def _detect_largest_face_roi(img):
    faces = detect_faces(img)
    if not faces: return img
    faces_sorted = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
    x, y, w, h = faces_sorted[0]
    x2 = min(img.shape[1], x + max(1, w))
    y2 = min(img.shape[0], y + max(1, h))
    roi = img[y:y2, x:x2]
    return roi if roi.size > 0 else img

# ============ Embedding 计算（优先 ArcFace，回退三哈希） ============
def _compute_embedding(face_img: np.ndarray) -> Optional[np.ndarray]:
    """计算 512维 ArcFace embedding，失败则返回 None"""
    if _load_arcface():
        emb = _af_embedding(face_img)
        if emb is not None and len(emb) == 512:
            return emb.astype(np.float32)
    return None

def _compute_hash_embedding(face_img: np.ndarray) -> np.ndarray:
    """三哈希 3072 位 embedding（bool 数组）"""
    return _triple_hash(face_img)

def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """余弦相似度（0~1），用于 ArcFace embedding"""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b) + 1e-10)
    return float(np.dot(a_norm, b_norm.T))

def _best_match(query_emb: np.ndarray, templates: np.ndarray, use_cosine: bool) -> float:
    """与模板库的最佳匹配度"""
    if len(templates) == 0:
        return 0.0
    if use_cosine:
        # ArcFace: 余弦相似度
        sims = np.array([_cosine_sim(query_emb, t) for t in templates])
        return float(np.max(sims))
    else:
        # 三哈希: top-3 均值汉明距离 → 转为相似度
        distances = np.array([_hamming(query_emb, t) for t in templates])
        top3 = np.sort(distances)[:3]
        return 1.0 - float(np.mean(top3))

# ============ 模板库构建 ============
def _build_master_embeddings(cfg: dict):
    if os.path.exists(MASTER_EMB_CACHE):
        loaded = np.load(MASTER_EMB_CACHE, allow_pickle=True)
        if len(loaded) > 0:
            return loaded

    use_arcface = _load_arcface()
    all_embs = []
    for item in cfg.get("master", []):
        img_path = os.path.normpath(os.path.join(FACE_DIR, item["file"].replace("/", os.sep)))
        img = _imread(img_path)
        if img is None: continue
        roi = _detect_largest_face_roi(img)
        
        # 数据增强（19 变体：原始 + 3亮度 × 6角度）
        if use_arcface:
            emb = _compute_embedding(roi)
            if emb is not None:
                all_embs.append(emb)
            rows, cols = roi.shape[:2]
            for bf in [0.7, 1.0, 1.4]:
                bright = roi.copy() if bf == 1.0 else cv2.convertScaleAbs(roi, alpha=bf, beta=0)
                for ang in [-15, -10, -5, 5, 10, 15]:
                    M = cv2.getRotationMatrix2D((cols/2, rows/2), ang, 1.0)
                    aug = cv2.warpAffine(bright, M, (cols, rows))
                    emb = _compute_embedding(aug)
                    if emb is not None:
                        all_embs.append(emb)
        else:
            all_embs.append(_compute_hash_embedding(roi))
            for aug in _augment_image(roi):
                all_embs.append(_compute_hash_embedding(aug))

    result = np.array(all_embs) if all_embs else np.array([])
    np.save(MASTER_EMB_CACHE, result)
    dim = "512维" if use_arcface else "3072位"
    print(f"[Face] 主人模板: {len(result)} 条（{dim}）")
    return result

def _build_others_embeddings(cfg: dict):
    if os.path.exists(OTHERS_EMB_CACHE):
        loaded = np.load(OTHERS_EMB_CACHE, allow_pickle=True).item()
        if loaded: return loaded

    use_arcface = _load_arcface()
    result = {}
    for name, val in cfg.get("others", {}).items():
        fp = val.get("file","") if isinstance(val,dict) else val
        rel = val.get("relation","") if isinstance(val,dict) else ""
        img_path = os.path.normpath(os.path.join(FACE_DIR, fp.replace("/", os.sep)))
        img = _imread(img_path)
        if img is None: continue
        roi = _detect_largest_face_roi(img)
        
        embs = []
        # 原始人脸 embedding
        if use_arcface:
            emb = _compute_embedding(roi)
            if emb is not None:
                embs.append(emb)
            # 数据增强（18 个变体：3亮度 × 6角度）
            rows, cols = roi.shape[:2]
            bf_values = [0.7, 1.0, 1.4]
            angle_values = [-15, -10, -5, 5, 10, 15]
            for bf in bf_values:
                if bf == 1.0:
                    bright = roi.copy()
                else:
                    bright = cv2.convertScaleAbs(roi, alpha=bf, beta=0)
                for ang in angle_values:
                    M = cv2.getRotationMatrix2D((cols/2, rows/2), ang, 1.0)
                    aug = cv2.warpAffine(bright, M, (cols, rows))
                    emb = _compute_embedding(aug)
                    if emb is not None:
                        embs.append(emb)
        else:
            embs = [_compute_hash_embedding(roi)]
            for aug in _augment_image(roi):
                embs.append(_compute_hash_embedding(aug))
        
        if embs:
            result[name] = (np.array(embs), rel)

    np.save(OTHERS_EMB_CACHE, result)
    return result

def _get_master_embeddings():
    if os.path.exists(MASTER_EMB_CACHE):
        return np.load(MASTER_EMB_CACHE, allow_pickle=True)
    cfg = _load_faces_config()
    return _build_master_embeddings(cfg)

def _get_others_embeddings():
    if os.path.exists(OTHERS_EMB_CACHE):
        return np.load(OTHERS_EMB_CACHE, allow_pickle=True).item()
    cfg = _load_faces_config()
    return _build_others_embeddings(cfg)

# ============ 人脸注册 ============
def _load_faces_config():
    if not os.path.exists(FACES_JSON): return {"master": [], "others": {}}
    with open(FACES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_faces_config(cfg):
    with open(FACES_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ============ 核心识别 ============
def recognize_face(face_img: np.ndarray) -> dict:
    use_arcface = _load_arcface()

    if use_arcface:
        q_emb = _compute_embedding(face_img)
        if q_emb is None:
            use_arcface = False
    if not use_arcface:
        q_emb = _compute_hash_embedding(face_img)

    # 1. 与主人模板匹配
    master_embs = _get_master_embeddings()
    master_sim = _best_match(q_emb, master_embs, use_arcface) if len(master_embs) > 0 else 0.0

    # 2. 与其他人模板匹配
    others_info = _get_others_embeddings()
    best_other_name, best_other_sim, best_other_rel = None, 0.0, ""
    for name, (embs_arr, rel) in others_info.items():
        if len(embs_arr) == 0: continue
        sim = _best_match(q_emb, embs_arr, use_arcface)
        if sim > best_other_sim:
            best_other_sim = sim
            best_other_name = name
            best_other_rel = rel

    # 3. 决策
    if use_arcface:
        # ArcFace 余弦相似度
        master_ok = master_sim >= MASTER_SIM
        other_ok = best_other_sim >= OTHER_SIM

        if master_ok and other_ok:
            # 两者都过阈值，比较差距：他人必须明显更接近自己的模板
            if best_other_sim > master_sim + 0.12:
                return {"name": best_other_name, "is_master": False,
                        "confidence": round(best_other_sim, 3), "relation": best_other_rel}
            else:
                return {"name": "主人", "is_master": True,
                        "confidence": round(master_sim, 3), "relation": ""}
        if master_ok:
            return {"name": "主人", "is_master": True,
                    "confidence": round(master_sim, 3), "relation": ""}
        if other_ok:
            return {"name": best_other_name, "is_master": False,
                    "confidence": round(best_other_sim, 3), "relation": best_other_rel}
        return {"name": "unknown", "is_master": False,
                "confidence": round(max(master_sim, best_other_sim), 3), "relation": ""}
    else:
        # 三哈希回退（原逻辑）
        MASTER_THRESH = 0.58
        OTHER_THRESH = 0.52
        master_dist = 1.0 - master_sim
        other_dist = 1.0 - best_other_sim
        master_ok = len(master_embs) > 0 and master_dist <= MASTER_THRESH
        other_ok = best_other_name and other_dist <= OTHER_THRESH

        if master_ok and other_ok:
            mr = master_dist / MASTER_THRESH
            o_r = other_dist / OTHER_THRESH
            if o_r < mr - 0.04:
                return {"name": best_other_name, "is_master": False,
                        "confidence": round(best_other_sim, 3), "relation": best_other_rel}
            elif mr < o_r - 0.08:
                return {"name": "主人", "is_master": True,
                        "confidence": round(master_sim, 3), "relation": ""}
            else:
                return {"name": "unknown", "is_master": False,
                        "confidence": round(max(master_sim, best_other_sim), 3), "relation": ""}
        if master_ok:
            return {"name": "主人", "is_master": True,
                    "confidence": round(master_sim, 3), "relation": ""}
        if other_ok:
            return {"name": best_other_name, "is_master": False,
                    "confidence": round(best_other_sim, 3), "relation": best_other_rel}
        return {"name": "unknown", "is_master": False,
                "confidence": round(max(master_sim, best_other_sim), 3), "relation": ""}

def recognize_faces_in_frame(frame: np.ndarray) -> list:
    lst = detect_faces(frame)
    results = []
    for (x, y, w, h) in lst:
        x2 = min(frame.shape[1], x + max(1, w))
        y2 = min(frame.shape[0], y + max(1, h))
        roi = frame[y:y2, x:x2]
        if roi.size == 0: continue
        rec = recognize_face(roi)
        rec["location"] = (x, y, w, h)
        results.append(rec)
    return results

def recognize_from_base64(img_b64: str) -> list:
    if img_b64.startswith("data:"): img_b64 = img_b64.split(",")[-1]
    nparr = np.frombuffer(base64.b64decode(img_b64), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None: return []
    return recognize_faces_in_frame(frame)

# ============ 人脸管理 ============
def add_master_face(image_path: str, desc: str = "") -> bool:
    cfg = _load_faces_config()
    ext = os.path.splitext(image_path)[1] or ".jpg"
    idx = len(cfg.get("master", [])) + 1
    new_name = f"{idx:03d}{ext}"
    new_path = os.path.join(MASTER_DIR, new_name)
    img = _imread(image_path)
    if img is None: return False
    _imwrite(new_path, img, ext)
    cfg.setdefault("master", []).append({"file": f"master/{new_name}", "desc": desc or f"第{idx}张主人照"})
    _save_faces_config(cfg)
    clear_cache()
    return True

def add_other_face(image_path: str, name: str, relation: str = "") -> bool:
    cfg = _load_faces_config()
    if name in cfg.get("others", {}): return False
    ext = os.path.splitext(image_path)[1] or ".jpg"
    new_name = f"{name}{ext}"
    new_path = os.path.join(OTHERS_DIR, new_name)
    img = _imread(image_path)
    if img is None: return False
    _imwrite(new_path, img, ext)
    cfg.setdefault("others", {})[name] = {"file": f"others/{new_name}", "relation": relation or ""}
    _save_faces_config(cfg)
    clear_cache()
    return True

def delete_face(name: str) -> bool:
    cfg = _load_faces_config()
    if name == "主人":
        cfg["master"] = []
        for f in os.listdir(MASTER_DIR): os.remove(os.path.join(MASTER_DIR, f))
    elif name in cfg.get("others", {}):
        val = cfg["others"][name]
        fp = val.get("file","") if isinstance(val, dict) else val
        full = os.path.join(FACE_DIR, fp)
        if os.path.exists(full): os.remove(full)
        del cfg["others"][name]
    else:
        return False
    _save_faces_config(cfg)
    clear_cache()
    return True

def clear_cache():
    if os.path.exists(CACHE_DIR):
        for f in os.listdir(CACHE_DIR): os.remove(os.path.join(CACHE_DIR, f))

def reload_known_faces():
    clear_cache()
    cfg = _load_faces_config()
    _build_master_embeddings(cfg)
    _build_others_embeddings(cfg)

def compute_known_faces_encodings(cfg):
    return _build_master_embeddings(cfg), _build_others_embeddings(cfg)

def get_all_known_faces():
    return {}, {}