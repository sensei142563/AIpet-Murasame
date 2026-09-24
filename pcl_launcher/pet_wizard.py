# -*- coding: utf-8 -*-
"""桌宠创建 / 设置 引导向导（分步，像安装向导一样一步步来）。

新建：桌宠页 → 「+ 添加新桌宠」→ 本向导
修改：桌宠卡片 → 「⚙ 设置」→ 同一个向导（预填现有配置）

步骤：
  1 基础信息（ID / 名称 / 简介 / 头像）
  2 形象类型（2D 立绘 / Live2D 模型）
  3 立绘素材（2D 时）：
      A 每个表情一张整图（简单，适合手绘单图）
      B 多图层拼合（像丛雨那样：表情/服装/发型/装饰分别一张图，拼成一张立绘）
  4 Live2D 模型（选 .model3.json，自动复制进角色包）
  5 语音（短语音=日语参考音频 GPT-SoVITS；长语音=中文参考音频 F5-TTS；可选默认模型）
  6 人设（短文本=桌宠 / 长文本=QQ；与「提示词」页同一份文件，双向同步）
  7 完成

向导只做「写文件 + 写 pet.json」，不依赖启动器其它模块，方便单独测试。
"""
import json
import os
import shutil
import sys

from PyQt5.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QFileDialog, QMessageBox, QStackedWidget, QListWidget, QListWidgetItem,
    QPlainTextEdit, QGroupBox, QRadioButton, QButtonGroup, QScrollArea, QWidget,
    QGridLayout, QSizePolicy, QSlider, QSpinBox
)
from PyQt5.QtGui import QFont, QPainter, QColor, QPixmap, QPen, QBrush, QPainterPath

from .colors import _app_base_dir  # noqa: F401  （打包时确保该模块被收集）
# 说明文字/状态字一律取主题色：写死的 #888 / #9a9aa8 / #8fd18f / #e07a90 / #7fc48f
# 都是深色 UI 时代的值，浅色主题（经典 / 千恋万花）上就是"浅字压浅底"看不清。
from .colors import Gray2, ok_text, warn_text  # noqa: F401

S = 1.0
EMOTION_PRESET = ["平静", "高兴", "害羞", "生气", "惊讶", "着急"]
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pets_dir() -> str:
    return os.path.join(_base_dir(), "pets")


# ══════════════════════ 纯逻辑部分（可单独测试）══════════════════════


def slugify_id(text: str) -> str:
    """把用户输入变成合法的桌宠 ID（文件夹名）"""
    import re
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^a-z0-9_\-]", "", t)
    return t


def parse_layer_index(idx_path: str) -> list:
    """解析立绘图层索引（丛雨格式：UTF-16LE 的 TSV）。

    返回 [{"name": 图层名, "id": 图层ID, "w": 宽, "h": 高}, ...]（按文件顺序）
    """
    import csv
    import io
    for enc in ("utf-16 le", "utf-16", "utf-8-sig", "gbk"):
        try:
            raw = open(idx_path, encoding=enc).read()
            break
        except Exception:
            raw = None
    if raw is None:
        return []
    rows = list(csv.reader(io.StringIO(raw), delimiter="\t"))
    out = []
    for r in rows:
        if len(r) < 10:
            continue
        name, lid = r[1].strip(), r[9].strip()
        if not name or not lid.isdigit():
            continue
        try:
            w, h = int(r[4] or 0), int(r[5] or 0)
        except Exception:
            w, h = 0, 0
        out.append({"name": name, "id": int(lid), "w": w, "h": h})
    return out


def find_index_files(fg_dir: str) -> list:
    """目录里的图层索引文件（*.txt，排除说明文件）"""
    if not os.path.isdir(fg_dir):
        return []
    return sorted(
        os.path.join(fg_dir, f) for f in os.listdir(fg_dir)
        if f.lower().endswith(".txt") and "说明" not in f
    )


def _cv_np():
    """取图片处理依赖（cv2 + numpy，随启动器一起打包）。

    缺失时给一句人话提示 —— 新建桌宠是普通操作，不该弹一堆 traceback。"""
    try:
        import cv2 as _cv
        import numpy as _np
        return _cv, _np
    except Exception as e:
        raise RuntimeError(
            f"启动器缺少图片处理组件（cv2 / numpy）：{e}\n"
            "请用官方安装包重新安装；若是绿色版，确认程序目录下 runtime/venv 与 _internal 完整。") from e


def write_single_image_pack(fg_dir: str, prefix: str, mapping: dict) -> tuple:
    """把「每个表情一张整图」转成图层素材包（和丛雨同格式，程序各处都能直接用）。

    mapping: {情绪名: 图片绝对路径}
    生成：<prefix>a.txt（索引） + <prefix>a_<图层ID>.png（每个情绪一张图层图）
    返回 (索引文件, {情绪: 图层ID})
    """
    cv2, np = _cv_np()
    os.makedirs(fg_dir, exist_ok=True)
    idx_path = os.path.join(fg_dir, f"{prefix}a.txt")
    layer_ids = {}
    base, w_max, h_max = 9000, 0, 0
    for i, (emo, src) in enumerate(mapping.items(), start=1):
        if not src or not os.path.exists(src):
            continue
        lid = base + i
        img = cv2.imdecode(np.fromfile(src, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        if img.shape[2] == 3:      # 没有透明通道 → 补一个不透明的
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        h, w = img.shape[:2]
        w_max, h_max = max(w_max, w), max(h_max, h)
        out_png = os.path.join(fg_dir, f"{prefix}a_{lid}.png")
        cv2.imencode(".png", img)[1].tofile(out_png)
        layer_ids[emo] = lid
    # 索引：表头 + 画布尺寸行 + 每个情绪一行（宽度/高度用实际图尺寸，位置 0,0）
    header = "#layer_type\tname\tleft\ttop\twidth\theight\ttype\topacity\tvisible\tlayer_id"
    lines = [header, f"\t\t\t\t{w_max}\t{h_max}\t\t\t\t"]
    for i, (emo, lid) in enumerate(layer_ids.items(), start=1):
        try:
            p = os.path.join(fg_dir, f"{prefix}a_{lid}.png")
            im = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            h, w = im.shape[:2]
        except Exception:
            w, h = w_max, h_max
        lines.append(f"0\t{emo}\t0\t0\t{w}\t{h}\t16\t255\t0\t{lid}\t\t\t")
    with open(idx_path, "wb") as f:      # 与丛雨索引一致：UTF-16LE + BOM
        f.write(("\ufeff" + "\n".join(lines) + "\n").encode("utf-16 le"))
    return idx_path, layer_ids


# 单图模式的 AI 选层提示词（让 AI 按句子情绪挑一张整图，返回它的编号）
_SINGLE_TEMPLATE = (
    "你是桌宠立绘选择助手。用户会提供一个句子列表，"
    "你需要根据每一个句子的情绪，从下面这些立绘里为每个句子挑一张最合适的。\n"
    "可选立绘：\n{layers_desc}\n\n"
    "返回 JSON 列表：每个句子一个数组，数组里只放一个编号。"
    "示例输出：{example}\n"
    "只返回 JSON，不要任何解释或多余文字。/no_think"
)


def write_portrait_prompts(path: str, spec: dict, log=print) -> bool:
    """按角色自己的立绘类型写 portrait_prompts.json（AI 选层提示词）。

    - single 模式：图层描述 = 表情名 → 表情图编号（AI 返回该编号即显示那张整图）
    - layers 模式：优先沿用「源角色包」的既有描述（用户从某个角色包导入的图层），
      找不到源就写一份通用的（AI 可在索引里挑基础人物/表情/头发）
    """
    kind = spec.get("kind")
    mode = spec.get("portrait_mode")
    sets = spec.get("portrait", {}).get("sets") or ["a"]
    set_name = sets[0] if sets else "a"
    prefix = str(spec.get("fgimages_prefix") or spec.get("id") or "").strip()

    if kind == "2d" and mode == "single":
        emo = (spec.get("portrait") or {}).get("emotions") or {}
        if not emo:
            return False
        desc = "表情 >> " + "；".join(f"{lid}：{name}" for name, lid in emo.items())
        first = (spec.get("portrait") or {}).get("default_emotion") or next(iter(emo))
        ex = "[" + ", ".join(f"[{int(lid)}]" for lid in list(emo.values())[:2]) + "]"
        data = {
            "prompt_template": _SINGLE_TEMPLATE,
            "sets": {set_name: {"layers_desc": desc, "example": ex,
                                "first_portrait": [int(emo.get(first, next(iter(emo.values()))))]}},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        log(f"已生成 AI 选层提示词（单图模式 · {len(emo)} 个表情）")
        return True

    # 图层模式：源目录若属于某个已有角色包 → 直接沿用它的描述（图层 ID 完全一致）
    src_dir = str(spec.get("layer_src_dir") or "")
    data = None
    try:
        pdir = os.path.dirname(os.path.abspath(src_dir)) if src_dir else ""
        cand = os.path.join(pdir, "portrait_prompts.json")
        if os.path.isfile(cand):
            data = json.load(open(cand, encoding="utf-8"))
    except Exception:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("sets"), dict):
        # 回退丛雨的模板（前缀对不上也没关系：AI 返回的 ID 不存在时，
        # 桌宠会回落到角色自己的默认立绘，不会崩）
        try:
            src_pp = os.path.join(pets_dir(), "murasame", "portrait_prompts.json")
            if os.path.isfile(src_pp):
                data = json.load(open(src_pp, encoding="utf-8"))
        except Exception:
            data = None
    if isinstance(data, dict) and isinstance(data.get("sets"), dict):
        # 只保留用到的套装，并把键名对齐成角色自己的套装名
        old = data["sets"]
        pick = old.get(set_name) or next(iter(old.values()), None)
        if isinstance(pick, dict):
            data["sets"] = {set_name: pick}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            log(f"已沿用源角色的 AI 选层提示词（套装 {set_name}）")
            return True
    return False


def _safe_copy(src: str, dst_path: str) -> bool:
    """安全复制文件：源和目标其实是同一个文件时直接跳过。

    ⚠ 编辑已有角色时，「音源目录」本来就是角色包自己的 voices/short →
    源 == 目标，shutil.copy2 会抛 SameFileError 把"保存"整条流程打断
    （用户看到的报错：'...\voices/short/害羞/ref.mp3' and '...\voices\short\害羞\ref.mp3'
     are the same file）。这里统一跳过 + 兜底，保存不再因此失败。
    """
    try:
        if not src or not os.path.exists(src):
            return False
        if os.path.exists(dst_path):
            try:
                if os.path.samefile(src, dst_path):
                    return False          # 同一个文件，什么都不用做
            except Exception:
                if os.path.abspath(src) == os.path.abspath(dst_path):
                    return False
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        if os.path.exists(dst_path):
            try:
                os.remove(dst_path)       # 覆盖旧文件（避免个别环境 copy2 覆盖失败）
            except Exception:
                pass
        try:
            shutil.copy2(src, dst_path)
        except shutil.SameFileError:
            return False
        except Exception:
            shutil.copy(src, dst_path)
        return True
    except Exception as e:
        print(f"[Wizard] ⚠ 复制文件失败（跳过）: {src} → {dst_path}: {e}")
        return False


def copy_short_voice_pack(src_dir: str, pet_voices_dir: str) -> tuple:
    """复制短语音包：源目录下每个情绪子目录（含参考音频 + asr.txt）→ 角色包 voices/short/

    返回 (情绪列表, 错误信息)。源就是目标目录时只做登记、不复制（编辑已有角色的常见情况）。
    """
    dst = os.path.join(pet_voices_dir, "short")
    if not src_dir or not os.path.isdir(src_dir):
        return [], "目录不存在"
    # 兼容两种结构：直接是情绪子目录 / 里面还有一层 short
    root = src_dir
    sub = os.path.join(src_dir, "short")
    if os.path.isdir(sub):
        root = sub
    _same_tree = False
    try:
        _same_tree = os.path.samefile(root, dst)
    except Exception:
        _same_tree = os.path.abspath(root) == os.path.abspath(dst)
    emotions = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d):
            continue
        refs = [f for f in os.listdir(d) if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg"))]
        if not refs:
            continue
        target = os.path.join(dst, name)
        os.makedirs(target, exist_ok=True)
        if not _same_tree:
            _safe_copy(os.path.join(d, refs[0]), os.path.join(target, refs[0]))
            asr = os.path.join(d, "asr.txt")
            if os.path.exists(asr):
                _safe_copy(asr, os.path.join(target, "asr.txt"))
            else:
                with open(os.path.join(target, "asr.txt"), "w", encoding="utf-8") as f:
                    f.write("")     # 没有文本也能跑（GPT-SoVITS 参考文本可空）
        else:
            # 源就是目标：只登记情绪（文件已经在正确位置）
            if not os.path.exists(os.path.join(target, "asr.txt")):
                with open(os.path.join(target, "asr.txt"), "w", encoding="utf-8") as f:
                    f.write("")
        emotions.append(name)
    return emotions, ("" if emotions else "没有找到带参考音频的情绪子目录")


def copy_short_voice_single(ref_path: str, ref_text: str, pet_voices_dir: str,
                            emotions: list = None) -> tuple:
    """单个参考音频 → 复制到每个情绪目录（同一音色，情绪由文字决定）

    同样用 _safe_copy：源和目标可能已经是同一个文件（编辑已有角色）。
    """
    dst = os.path.join(pet_voices_dir, "short")
    emos = [e for e in (emotions or EMOTION_PRESET) if e]
    if not ref_path or not os.path.exists(ref_path):
        return [], "参考音频不存在"
    for e in emos:
        d = os.path.join(dst, e)
        os.makedirs(d, exist_ok=True)
        _safe_copy(ref_path, os.path.join(d, os.path.basename(ref_path)))
        with open(os.path.join(d, "asr.txt"), "w", encoding="utf-8") as f:
            f.write((ref_text or "").strip())
    return emos, ""


def default_long_ref() -> tuple:
    """默认长语音参考（全局兜底，随程序分发）"""
    p = os.path.join(_base_dir(), "reference_voices", "long_chinese", "953244.wav")
    txt = "能和老师在一起，我真的，好高兴！"
    return (p if os.path.exists(p) else "", txt)


def build_pet_json(spec: dict, existing: dict = None) -> dict:
    """把向导收集的信息写成 pet.json（保留原有未知字段）"""
    cfg = dict(existing or {})
    pid = spec["id"]
    cfg.update({
        "id": pid,
        "name": spec.get("name") or pid,
        "display_name": spec.get("display_name") or spec.get("name") or pid,
        "intro": spec.get("intro") or cfg.get("intro", ""),
        "avatar": spec.get("avatar") or cfg.get("avatar", ""),
        "prompt": {
            "short": spec.get("prompt_short_file") or "prompt.txt",
            "long": spec.get("prompt_long_file") or "longtext_prompt.txt",
        },
        "languages": {"primary": "ja", "secondary": "zh", "dialog_language": "zh"},
        "sticker": {"dir": "biaoqingbao/"},
        "memory": {"isolated": True, "dir": "memory/"},
        "capabilities": {
            "chat": True, "screen_vision": True, "camera_vision": True,
            "face_recognition": True, "qq": True,
            "short_tts": bool(spec.get("short_emotions")),
            "long_tts": bool(spec.get("long_ref_audio")),
        },
    })
    m = dict(cfg.get("model") or {})
    if spec.get("kind") == "live2d":
        m["default"] = "live2d"
        m["has_live2d"] = True
        m["live2d_dir"] = "live2d/"
        m.setdefault("live2d_scale", 1.0)
        m.setdefault("live2d_offset_x", 0.0)
        m.setdefault("live2d_offset_y", 0.0)
        if spec.get("live2d_model"):
            m["live2d_model"] = spec["live2d_model"]
    else:
        m["default"] = "2d"
        m["has_live2d"] = bool(m.get("has_live2d"))
        m["has_fgimages"] = True
        # 前缀留空 → 自动用角色 ID（与生成的素材文件名一致）。
        # ⚠ 以前留空会让桌宠退回「ムラサメ」前缀找索引 → 找不到 → 启动崩溃、桌宠不出现。
        m["fgimages_prefix"] = (str(spec.get("fgimages_prefix") or "").strip()
                               or str(spec.get("id") or "").strip())
        m["fgimages_sets"] = ["a"]
    # ── 显示与对话框：2D / Live2D 两套独立设置 ──
    try:
        d2 = dict(spec.get("display_2d") or {})
        dl = dict(spec.get("display_live2d") or {})
        if spec.get("display_mode"):
            m["default"] = "live2d" if spec["display_mode"] == "live2d" else "2d"
        if d2:
            m["display_2d"] = {k: d2.get(k) for k in ("height_ratio", "scale", "offset_x", "offset_y")
                               if d2.get(k) is not None}
        if dl:
            m["display_live2d"] = {k: dl.get(k) for k in ("height_ratio", "width_ratio", "scale",
                                                        "offset_x", "offset_y")
                                   if dl.get(k) is not None}
            if dl.get("height_ratio") is not None:
                m["live2d_window_height_ratio"] = round(float(dl["height_ratio"]), 3)
            if dl.get("width_ratio") is not None:
                m["live2d_window_ratio"] = round(float(dl["width_ratio"]), 3)
        # 两套立绘声明（a 侧面 / b 正面）：只有一套时不让界面出 a/b 切换
        sets = [str(x) for x in (spec.get("sets") or ["a"])]
        m["fgimages_sets"] = sets
        m["sets_available"] = sets
        m["set_labels"] = {"a": "侧面立绘", "b": "正面立绘"}
        # 图层微调（防止穿模）
        pend = spec.get("layer_adjust_pending")
        if isinstance(pend, dict) and pend:
            adj = dict(m.get("layer_adjust") or {})
            adj[str((spec.get("sets") or ["a"])[0])] = pend
            m["layer_adjust"] = adj
    except Exception as e:
        print(f"[Wizard] ⚠ 写入显示设置失败: {e}")
    cfg["model"] = m
    # 对话框区域 / 字号：2D 与 Live2D **各存一份**（互不影响）
    try:
        inter = dict(cfg.get("interaction") or {})
        d2 = dict(spec.get("display_2d") or {})
        dl = dict(spec.get("display_live2d") or {})
        if d2.get("text_box"):
            inter["text_box_2d"] = [round(float(v), 3) for v in d2["text_box"][:4]]
            inter["text_font_scale_2d"] = round(float(d2.get("font_scale") or 1.0), 2)
        if dl.get("text_box"):
            inter["text_box_live2d"] = [round(float(v), 3) for v in dl["text_box"][:4]]
            inter["text_font_scale_live2d"] = round(float(dl.get("font_scale") or 1.0), 2)
        # 兼容旧键（老版本读 text_box / text_font_scale）
        if inter.get("text_box_2d"):
            inter["text_box"] = inter["text_box_2d"]
        if inter.get("text_font_scale_2d") is not None:
            inter["text_font_scale"] = inter["text_font_scale_2d"]
        if inter:
            cfg["interaction"] = inter
    except Exception as e:
        print(f"[Wizard] ⚠ 写入对话框设置失败: {e}")
    # 触摸互动开关（九个部位的「范围」由「触摸互动」页的编辑器单独保存到 touch.areas）
    try:
        t = dict(cfg.get("touch") or {})
        chk = getattr(self, "chk_touch", None)
        if chk is not None:
            t["enabled"] = bool(chk.isChecked())
        # ⚠ 只在"确实要开触摸"（勾了开关）或"本来就配过区域"时才补默认范围。
        #   以前这里无条件给每个角色塞一套 14 个通用框 → 等于"没做过的角色也开了触摸"，
        #   而且通用框对 Live2D 全身模型位置全是错的（用户要的是：没做的不开）。
        if t.get("enabled") or any(t.get(k) for k in ("areas", "areas_2d", "areas_live2d")):
            # 2D 与 Live2D **各写一套**默认范围（两套独立，互不影响；之后可在编辑器里分别调）
            try:
                from tool.touch_areas import defaults as _ta_defaults
                _d = _ta_defaults()
                t.setdefault("areas_2d", dict(_d))
                t.setdefault("areas_live2d", dict(_d))
                t.setdefault("disabled_2d", [])
                t.setdefault("disabled_live2d", [])
                if not t.get("areas"):
                    t["areas"] = dict(_d)        # 旧键兼容
            except Exception as _e:
                print(f"[Wizard] ⚠ 写入默认触摸范围失败: {_e}")
        else:
            print("[Wizard] 未启用触摸互动 → 不写默认触摸区域（保持「没做过就不开」）")
        cfg["touch"] = t
    except Exception as e:
        print(f"[Wizard] ⚠ 写入触摸设置失败: {e}")
    v = dict(cfg.get("voices") or {})
    v["short_emotions"] = list(spec.get("short_emotions") or [])
    v["short_ref_dir"] = "voices/short/"
    v["long_ref_audio"] = spec.get("long_ref_audio") or ""
    v["long_ref_text"] = spec.get("long_ref_text") or ""
    if spec.get("default_emotion"):
        v["default_emotion"] = spec["default_emotion"]
    cfg["voices"] = v
    if spec.get("portrait"):
        cfg["portrait"] = spec["portrait"]
    return cfg


def create_or_update_pet(spec: dict, log=print) -> tuple:
    """落盘：建目录、写 pet.json、写人设、复制语音/立绘/模型素材。

    返回 (pet_id, 提示信息列表)
    """
    pid = spec["id"]
    dst = os.path.join(pets_dir(), pid)
    tpl = os.path.join(pets_dir(), "_template")
    is_new = not os.path.exists(os.path.join(dst, "pet.json"))
    notes = []
    os.makedirs(dst, exist_ok=True)
    for d in ("fgimages", "live2d", "voices", "memory", "biaoqingbao"):
        os.makedirs(os.path.join(dst, d), exist_ok=True)
    if is_new and os.path.isdir(tpl):
        # 模板里只有 pet.json / prompt.txt，仅作占位，不覆盖已写内容
        for f in ("pet.json", "prompt.txt"):
            src = os.path.join(tpl, f)
            if os.path.exists(src) and not os.path.exists(os.path.join(dst, f)):
                _safe_copy(src, os.path.join(dst, f))

    # 人设文本
    ps_path = os.path.join(dst, "prompt.txt")
    pl_path = os.path.join(dst, "longtext_prompt.txt")
    if spec.get("prompt_short") is not None:
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(spec.get("prompt_short") or "")
    elif not os.path.exists(ps_path):
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(f"你叫{spec.get('name') or pid}，是一个住在用户电脑里的AI桌宠角色。\n")
    if spec.get("prompt_long") is not None:
        with open(pl_path, "w", encoding="utf-8") as f:
            f.write(spec.get("prompt_long") or "")
    elif not os.path.exists(pl_path):
        shutil.copy2(ps_path, pl_path)
    # 立绘图层提示词模板（AI 选层用）
    # ⚠ 旧实现把丛雨的模板整体复制过来、并把 sets 写成 ["a"]（列表）→
    #   桌宠侧读 sets.get(...) 直接 AttributeError，启动就崩；而且描述还是丛雨的图层。
    #   现在按角色自己的立绘类型生成：单图模式=表情表，图层模式=沿用源角色的描述。
    # 2D 立绘素材
    if spec.get("kind") == "2d" and spec.get("portrait_mode") == "single":
        mapping = spec.get("emotion_images") or {}
        if mapping:
            prefix = spec.get("fgimages_prefix") or pid
            idx, layer_ids = write_single_image_pack(
                os.path.join(dst, "fgimages"), prefix, mapping)
            notes.append(f"已生成立绘素材：{os.path.basename(idx)}（{len(layer_ids)} 个表情）")
            # ★ 必须写 portrait 块：立绘合成/表情表都按它走，
            #   否则会退回内置（丛雨）表 → 新角色合成必然失败
            first = next(iter(layer_ids), "平静")
            spec["portrait"] = {
                "mode": "single",
                "prefix": prefix,
                "sets": ["a"],
                "emotions": {k: int(v) for k, v in layer_ids.items()},
                "default_emotion": ("平静" if "平静" in layer_ids else first),
                "clothes": {},
                "decors": {},
            }
    elif spec.get("kind") == "2d" and spec.get("portrait_mode") == "layers":
        # 把源目录里该前缀的索引与图层图复制进角色包
        src_dir = spec.get("layer_src_dir") or ""
        prefix = spec.get("fgimages_prefix") or ""
        n = 0
        if src_dir and os.path.isdir(src_dir):
            for f in os.listdir(src_dir):
                if f.startswith(prefix) and (f.lower().endswith(".png") or f.lower().endswith(".txt")):
                    _safe_copy(os.path.join(src_dir, f), os.path.join(dst, "fgimages", f))
                    n += 1
            if n:
                notes.append(f"已导入 {n} 个图层素材（前缀 {prefix}）")
            else:
                notes.append(f"⚠ 源目录里没有以「{prefix}」开头的图层文件，请稍后手动放入 fgimages/")

    # Live2D 模型
    if spec.get("kind") == "live2d" and spec.get("live2d_src"):
        src = spec["live2d_src"]
        target = os.path.join(dst, "live2d")
        try:
            if os.path.isdir(src):
                for item in os.listdir(src):
                    s, t = os.path.join(src, item), os.path.join(target, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, t, dirs_exist_ok=True)
                    else:
                        _safe_copy(s, t)
            else:
                _safe_copy(src, os.path.join(target, os.path.basename(src)))
            notes.append("Live2D 模型已复制进角色包")
        except Exception as e:
            notes.append(f"⚠ Live2D 模型复制失败: {e}")

    # 立绘 AI 选层提示词（portrait_prompts.json）——必须放在立绘素材处理之后：
    # 单图模式要拿 spec["portrait"]["emotions"] 里的「表情名 → 编号」来写描述。
    pp = os.path.join(dst, "portrait_prompts.json")
    try:
        need = not os.path.exists(pp)
        if not need and spec.get("portrait_mode") == "single":
            # 老版本可能留下「sets 是列表 / 描述还是丛雨图层」的坏文件 → 单图模式直接重写修复
            try:
                _d = json.load(open(pp, encoding="utf-8"))
                need = (not isinstance(_d.get("sets"), dict)
                        or "表情" not in json.dumps(_d.get("sets"), ensure_ascii=False))
            except Exception:
                need = True
        if need:
            write_portrait_prompts(pp, spec, log=log)
    except Exception as e:
        log(f"⚠ 生成立绘提示词失败: {e}")

    # 语音
    if spec.get("short_voice_dir"):
        emos, err = copy_short_voice_pack(spec["short_voice_dir"], os.path.join(dst, "voices"))
        spec["short_emotions"] = emos
        notes.append(f"短语音(日语)：导入 {len(emos)} 个情绪" + (f"（{err}）" if err else ""))
    elif spec.get("short_voice_single"):
        emos, err = copy_short_voice_single(spec["short_voice_single"],
                                            spec.get("short_voice_text", ""),
                                            os.path.join(dst, "voices"),
                                            spec.get("short_voice_emotions"))
        spec["short_emotions"] = emos
        notes.append(f"短语音(日语)：单一音色导入 {len(emos)} 个情绪" + (f"（{err}）" if err else ""))
    if spec.get("long_ref_src"):
        try:
            os.makedirs(os.path.join(dst, "voices", "long"), exist_ok=True)
            tgt = os.path.join(dst, "voices", "long", os.path.basename(spec["long_ref_src"]))
            _safe_copy(spec["long_ref_src"], tgt)
            spec["long_ref_audio"] = f"voices/long/{os.path.basename(spec['long_ref_src'])}"
            notes.append("长语音(中文)：参考音频已导入")
        except Exception as e:
            notes.append(f"⚠ 长语音参考音频复制失败: {e}")

    # 头像：没给就尝试用立绘第一张图替代
    if spec.get("avatar_src") and os.path.exists(spec["avatar_src"]):
        try:
            ext = os.path.splitext(spec["avatar_src"])[1] or ".png"
            _safe_copy(spec["avatar_src"], os.path.join(dst, "avatar" + ext))
            spec["avatar"] = "avatar" + ext
            notes.append("头像已设置")
        except Exception as e:
            notes.append(f"⚠ 头像复制失败: {e}")

    # 写 pet.json
    existing = None
    pj = os.path.join(dst, "pet.json")
    if os.path.exists(pj):
        try:
            existing = json.load(open(pj, encoding="utf-8"))
        except Exception:
            existing = None
    cfg = build_pet_json(spec, existing)
    try:
        json.dump(cfg, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception as e:
        return pid, [f"❌ 写入 pet.json 失败: {e}"]

    # 注册到角色列表
    try:
        from pets.pet_registry import register_pet, scan_pets
        register_pet(pid)
        scan_pets()
    except Exception as e:
        log(f"⚠ 注册角色失败: {e}")
    return pid, notes


# ══════════════════════ 向导界面 ══════════════════════
from .silicon_dialog import SiliconDialog, page_msg, page_confirm  # noqa: E402


class DisplayPreview(QWidget):
    """「显示与对话框」实时预览：屏幕示意 + 桌宠窗口（按占屏高度）+ 立绘 + 对话框区域。

    - 鼠标可直接拖动对话框区域调位置（归一化坐标，写进 pet.json 的 interaction.text_box）
    - 参数一变就重画 → 所见即所得
    """

    def __init__(self, wizard, parent=None):
        super().__init__(parent)
        self.wiz = wizard
        self.setMinimumSize(340, 280)
        self.bx, self.by, self.bw, self.bh = 0.06, 0.05, 0.88, 0.40
        self.height_ratio = 0.45
        self.scale = 1.0                 # 立绘整体缩放（左右画布实时反映）
        self.ox = 0                      # 水平偏移（窗口内）
        self.oy = 0                      # 垂直偏移（窗口内）
        self.font_scale = 1.0            # 对话框字号系数（框内文字大小随之变化）
        self.width_ratio = None          # Live2D 的窗口宽高比（None = 跟随立绘比例）
        self.pix = QPixmap()
        self.mode = "2d"                 # 2d / live2d
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def set_mode(self, mode: str):
        self.mode = "live2d" if str(mode) == "live2d" else "2d"
        self.update()

    def set_box(self, x, y, w=None, h=None):
        self.bx = max(0.0, min(0.98, float(x)))
        self.by = max(0.0, min(0.98, float(y)))
        if w is not None:
            self.bw = max(0.05, min(1.0, float(w)))
        if h is not None:
            self.bh = max(0.05, min(1.0, float(h)))
        self.update()

    def set_params(self, values: dict, pixmap: QPixmap):
        tb = values.get("text_box") or [self.bx, self.by, self.bw, self.bh]
        try:
            self.bx, self.by, self.bw, self.bh = [float(v) for v in tb[:4]]
        except Exception:
            pass
        # ★ 立绘缩放 / 偏移 / 对话框字号：以前套了参数但画布不用 → 调了看不到变化
        try:
            self.scale = max(0.2, min(3.0, float(values.get("scale") or 1.0)))
        except Exception:
            self.scale = 1.0
        try:
            self.ox = int(values.get("offset_x") or 0)
            self.oy = int(values.get("offset_y") or 0)
        except Exception:
            self.ox = self.oy = 0
        try:
            self.font_scale = max(0.4, min(3.0, float(values.get("font_scale") or 1.0)))
        except Exception:
            self.font_scale = 1.0
        self.height_ratio = float(values.get("height_ratio") or 0.45)
        try:
            wr = values.get("width_ratio")
            self.width_ratio = float(wr) if wr else None
        except Exception:
            self.width_ratio = None
        if pixmap is not None and not pixmap.isNull():
            self.pix = pixmap
        self.update()

    def _screen_rect(self) -> QRect:
        m = 10
        return QRect(m, m, max(40, self.width() - 2 * m), max(40, self.height() - 2 * m))

    def _pet_rect(self) -> QRect:
        s = self._screen_rect()
        h = max(40, int(s.height() * self.height_ratio))
        w = h
        if self.mode == "live2d" and self.width_ratio:
            # Live2D：窗口按角色的宽高比（模型本身是方的/半身的都常见）
            w = max(30, int(h * float(self.width_ratio)))
        elif self.pix is not None and not self.pix.isNull() and self.pix.height() > 0:
            w = max(30, int(h * self.pix.width() / float(self.pix.height())))
        w = min(w, s.width())
        x = s.x() + max(0, (s.width() - w) // 2)
        y = s.y() + max(0, s.height() - h)
        return QRect(x, y, w, h)

    def paintEvent(self, event):
        # ⚠ Qt 里 paintEvent 抛异常 = 整个程序直接 abort（不是普通报错）→ 全程兜底
        try:
            self._paint(event)
        except Exception as e:
            print(f"[Wizard] ⚠ 预览绘制失败: {e}")

    def _paint(self, event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.fillRect(self.rect(), QColor("#1b1b22"))
            s = self._screen_rect()
            p.setPen(QPen(QColor("#3a3a46"), 1))
            p.setBrush(QBrush(QColor("#23232c")))
            p.drawRoundedRect(s, 8, 8)
            p.setPen(QPen(QColor("#7a7a8c"), 1))
            p.drawText(s.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignTop,
                       f"屏幕示意 · 桌宠占屏高 {int(self.height_ratio * 100)}%")

            pr = self._pet_rect()
            if self.mode == "live2d":
                # Live2D：画一个「模型区」示意图（实时画面在立绘工坊里看）
                p.setPen(QPen(QColor("#5a6bb0"), 1, Qt.DashLine))
                p.setBrush(QBrush(QColor(90, 107, 176, 40)))
                p.drawRect(pr)
                p.setPen(QColor("#9fb0e8"))
                p.drawText(pr, Qt.AlignCenter, "Live2D 模型区\n（大小 / 位置按右侧设置）")
            if (self.mode != "live2d" and self.pix is not None
                    and not self.pix.isNull() and pr.width() > 0 and pr.height() > 0):
                # 立绘：按窗口比例放入 → 再套「整体缩放」和「偏移」（调了立刻能看到）
                scaled = self.pix.scaled(pr.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                if abs(getattr(self, "scale", 1.0) - 1.0) > 0.001:
                    scaled = scaled.scaled(
                        max(8, int(scaled.width() * self.scale)),
                        max(8, int(scaled.height() * self.scale)),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
                _off = _oyy = 0
                if pr.height() > 0:
                    _off = int(self.ox * pr.height() / 864.0 * 1.0)
                    _oyy = int(self.oy * pr.height() / 864.0 * 1.0)
                p.save()
                p.setClipRect(pr)          # 超出窗口的部分裁掉（和桌宠一致）
                p.drawPixmap(pr.x() + (pr.width() - scaled.width()) // 2 + _off,
                             pr.y() + (pr.height() - scaled.height()) // 2 + _oyy, scaled)
                p.restore()
            p.setPen(QPen(QColor("#6f7bd0"), 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(pr)

            bx = pr.x() + int(pr.width() * self.bx)
            by = pr.y() + int(pr.height() * self.by)
            bw = max(20, int(pr.width() * self.bw))
            bh = max(14, int(pr.height() * self.bh))
            box = QRect(bx, by, bw, bh)
            path = QPainterPath()
            # ⚠ 必须用 QRectF / 分开传坐标：PyQt5 不接受 QRect
            path.addRoundedRect(float(box.x()), float(box.y()),
                                float(box.width()), float(box.height()), 6.0, 6.0)
            p.fillPath(path, QColor(80, 150, 255, 60))
            p.setPen(QPen(QColor("#4ea1ff"), 2))
            p.drawPath(path)
            # 框里的字：大小跟着「字号」滑块变 → 直观看到字有多大
            try:
                _fs = max(7, int(round(12 * float(getattr(self, "font_scale", 1.0)))))
                _f = QFont(self.font())
                _f.setPixelSize(_fs)
                p.setFont(_f)
            except Exception:
                pass
            p.setPen(QColor("#cfe4ff"))
            p.drawText(box, Qt.AlignCenter,
                       f"对话框区域\n(可拖动) 字号≈{max(7, int(12 * float(getattr(self, 'font_scale', 1.0))))}px")
        finally:
            p.end()

    def mousePressEvent(self, event):
        pr = self._pet_rect()
        box = QRect(pr.x() + int(pr.width() * self.bx), pr.y() + int(pr.height() * self.by),
                    max(20, int(pr.width() * self.bw)), max(14, int(pr.height() * self.bh)))
        if box.contains(event.pos()):
            self._drag = (event.pos().x() - box.x(), event.pos().y() - box.y())
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if not self._drag:
            return
        pr = self._pet_rect()
        if pr.width() <= 0 or pr.height() <= 0:
            return
        nx = (event.pos().x() - self._drag[0] - pr.x()) / float(pr.width())
        ny = (event.pos().y() - self._drag[1] - pr.y()) / float(pr.height())
        self.bx = max(0.0, min(1.0 - self.bw, nx))
        self.by = max(0.0, min(1.0 - self.bh, ny))
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)


class _LayerTuneDialog(QDialog):
    """图层位置 / 大小微调（防穿模）。

    分类：服装 / 表情 / 头发 / 装饰 / 基础人物 —— 分别给 X、Y 偏移与缩放；
    保存进 pet.json 的 model.layer_adjust.<套>，桌面立绘与 QQ 立绘共用。
    """

    CATS = (("cloth", "服装（身体层）"), ("expr", "表情"), ("hair", "头发"),
            ("decor", "装饰"), ("base", "基础人物"))

    def __init__(self, wizard, disp: dict, preview_getter, parent=None):
        super().__init__(parent or wizard)
        self.wizard = wizard
        self.setWindowTitle("图层位置微调（防穿模）")
        self.resize(600, 480)
        self._preview_getter = preview_getter
        self._set_name = str((disp.get("2d") or {}).get("preview_set") or "a")
        self._vals = {}

        root = QVBoxLayout(self)
        tip = QLabel("调整某类图层的位置 / 大小：例如服装偏了、表情偏上、饰品穿模。\n"
                     "改动会写进角色配置，桌面立绘与 QQ 立绘同时生效。")
        tip.setWordWrap(True)
        root.addWidget(tip)

        self.lbl_applied = QLabel("")
        self.lbl_applied.setStyleSheet(f"color:{ok_text().name()};font-size:12px;")
        self.lbl_applied.setWordWrap(True)
        self.preview = QLabel("（点「刷新预览」看效果）")
        self.preview.setMinimumHeight(220)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background:#23232e;color:#9a9aa8;border-radius:8px;")
        root.addWidget(self.preview, 1)

        form = QGridLayout()
        for i, (key, label) in enumerate(self.CATS):
            dx = QSpinBox(); dx.setRange(-300, 300)
            dy = QSpinBox(); dy.setRange(-300, 300)
            sc = QSpinBox(); sc.setRange(50, 200); sc.setValue(100)
            form.addWidget(QLabel(label), i, 0)
            form.addWidget(QLabel("X"), i, 1); form.addWidget(dx, i, 2)
            form.addWidget(QLabel("Y"), i, 3); form.addWidget(dy, i, 4)
            form.addWidget(QLabel("缩放%"), i, 5); form.addWidget(sc, i, 6)
            self._vals[key] = [dx, dy, sc]
        root.addLayout(form)

        bar = QHBoxLayout()
        btn_refresh = QPushButton("🔄 刷新预览")
        btn_reset = QPushButton("♻ 恢复默认（全部归零）")
        btn_ok = QPushButton("✅ 应用")
        btn_cancel = QPushButton("取消")
        btn_refresh.clicked.connect(self.refresh)
        btn_reset.clicked.connect(self._reset_all)
        btn_ok.clicked.connect(self._apply)
        btn_cancel.clicked.connect(self.reject)
        bar.addWidget(btn_refresh); bar.addWidget(btn_reset)
        bar.addStretch(); bar.addWidget(btn_ok); bar.addWidget(btn_cancel)
        root.addLayout(bar)

        self._load_current()
        # 改动即刷新预览，但用 350ms 防抖（合成要走子进程，太频繁会卡）
        self._deb = QTimer(self)
        self._deb.setSingleShot(True)
        self._deb.timeout.connect(self.refresh)
        for wids in self._vals.values():
            for w in wids:
                w.valueChanged.connect(lambda *_: self._deb.start(350))

    def _adj_table(self) -> dict:
        try:
            from pets.pet_registry import get_pet_config
            m = (get_pet_config(self.wizard.pet_id).get("model") or {})
            return dict(((m.get("layer_adjust") or {}).get(self._set_name)) or {})
        except Exception:
            return {}

    def _load_current(self):
        try:
            cfg = self._adj_table()
            for key, wids in self._vals.items():
                v = cfg.get(key) or [0, 0, 1.0]
                wids[0].setValue(int(v[0]))
                wids[1].setValue(int(v[1]))
                wids[2].setValue(int(round(float(v[2]) * 100)))
        except Exception as e:
            print(f"[LayerTune] ⚠ 载入微调失败: {e}")

    def _collect_table(self) -> dict:
        out = {}
        for key, wids in self._vals.items():
            dx, dy, sc = wids[0].value(), wids[1].value(), wids[2].value() / 100.0
            if dx or dy or abs(sc - 1.0) > 0.001:
                out[key] = [dx, dy, round(sc, 3)]
        return out

    def _reset_all(self):
        for wids in self._vals.values():
            wids[0].setValue(0); wids[1].setValue(0); wids[2].setValue(100)
        self.refresh()

    def refresh(self):
        try:
            tbl = {self._set_name: self._collect_table()}
            os.environ["AIPET_LAYER_ADJUST"] = json.dumps(tbl, ensure_ascii=False)
            if self.wizard.pet_id:
                os.environ["AIPET_PET_ID"] = self.wizard.pet_id
            self.wizard._live_layer_adjust = tbl      # 让采集/预览都用这份
            try:
                self.wizard._refresh_display_preview()   # 向导左侧预览同步刷新（改完立刻能看到）
            except Exception:
                pass
            try:
                tbl = self._collect_table()
                txt = "；".join(f"{dict(self.CATS).get(k, k)}({v[0]},{v[1]},{int(v[2]*100)}%)"
                                for k, v in tbl.items())
                self.lbl_applied.setText(("✅ 已应用微调：" + txt) if txt else "（当前全部为 0 / 100%）")
            except Exception:
                pass
            pix = self._preview_getter()
            if pix is not None and not pix.isNull():
                self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio,
                                                  Qt.SmoothTransformation))
                self.preview.setText("")
            else:
                self.preview.setText("（没有可用的立绘素材）")
        except Exception as e:
            print(f"[LayerTune] ⚠ 刷新预览失败: {e}")

    def _apply(self):
        try:
            from pets.pet_registry import get_active_pet_id, get_pet_dir
            pid = self.wizard.pet_id or get_active_pet_id()
            path = os.path.join(get_pet_dir(pid), "pet.json")
            cfg = json.load(io.open(path, encoding="utf-8"))
            m = cfg.setdefault("model", {})
            adj = dict(m.get("layer_adjust") or {})
            tbl = self._collect_table()
            if tbl:
                adj[self._set_name] = tbl
            else:
                adj.pop(self._set_name, None)
            m["layer_adjust"] = adj
            json.dump(cfg, io.open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[LayerTune] 已保存 {self._set_name} 套微调: {tbl}")
            self.accept()
        except Exception as e:
            page_msg(self, "保存失败", str(e))


class PCLPetWizard(SiliconDialog):
    """分步引导：新建 / 设置 桌宠"""

    saved = pyqtSignal(str)      # 保存完成（pet_id）

    STEPS = ["基础信息", "形象类型", "立绘素材", "Live2D 模型", "显示与对话框",
             "触摸互动", "语音", "人设", "完成"]
    # 每个步骤只对某些形象类型有效（用于自动跳过 + 点左边列表时的落点）
    STEP_ONLY = {2: "2d", 3: "live2d"}

    def __init__(self, pet_id: str = None, parent=None):
        super().__init__(parent)
        self.pet_id = pet_id
        self.is_edit = bool(pet_id)
        self._is_edit = self.is_edit
        self._spec = {"emotion_images": {}, "short_voice_emotions": []}
        self._layers = []
        self._cloth_added = False
        _title = ("设置桌宠：" + (pet_id or "")) if self._is_edit else "添加新桌宠（引导）"
        # 窗口放大（内容显示不全/要滑滚动条很麻烦）：默认 1280x900，并加大最小尺寸
        self._want_size = (1280, 900)
        super().__init__(_title, parent, width=1280, height=900)
        self.setWindowTitle(_title)
        try:
            self.setMinimumSize(1120, 780)
        except Exception:
            pass
        self._build()
        if self.is_edit:
            self._load_existing()
        # ⚠ 无边框窗口第一次显示时容易用「最小尺寸」→ 看着很小、动一下才变大。
        #   显示后再强制按目标尺寸布局一次（并让子控件重新排布）。
        try:
            self.resize(*self._want_size)
            QTimer.singleShot(0, self._force_size)
            QTimer.singleShot(120, self._force_size)
        except Exception as _e:
            print(f"[Wizard] ⚠ 初始尺寸设置失败: {_e}")

    def showEvent(self, event):
        """窗口真正显示后再强制尺寸（否则会"要挪一下才变大"）"""
        super().showEvent(event)
        try:
            w, h = getattr(self, "_want_size", (1280, 900))
            self.resize(w, h)
            QTimer.singleShot(0, self._force_size)
            QTimer.singleShot(120, self._force_size)
        except Exception as _e:
            print(f"[Wizard] ⚠ showEvent 尺寸失败: {_e}")

    def _force_size(self):
        """按目标尺寸强制布局一次。

        ⚠ 改尺寸后必须同时做三件事，否则会出现「按钮显示的位置和能点的位置不一样」：
        ① 重排所有布局；② clearMask() 清掉 Windows 残留的旧窗口区域；③ 重绘。
        """
        try:
            w, h = getattr(self, "_want_size", (1280, 900))
            self.resize(w, h)
            try:
                lay = self.layout()
                if lay is not None:
                    lay.activate()
                c = getattr(self, "content", None)
                if c is not None:
                    c.invalidate()
                    c.activate()
            except Exception:
                pass
            for c in (getattr(self, "content", None), getattr(self, "disp_preview", None)):
                try:
                    c.updateGeometry()
                except Exception:
                    pass
            try:
                self.clearMask()
            except Exception:
                pass
            self.update()
            print(f"[Wizard] 已按 {w}x{h} 重新布局（当前 {self.width()}x{self.height()}）")
        except Exception as e:
            print(f"[Wizard] ⚠ 强制尺寸失败: {e}")

    # ── 界面骨架 ──
    def _build(self):
        root = self.content
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        head = QLabel("🧭 跟着向导走完这几步，就能拥有自己的桌宠")
        head.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        root.addWidget(head)

        body = QHBoxLayout()
        # 左侧步骤
        self.step_list = QListWidget()
        self.step_list.setFixedWidth(150)
        self.step_list.addItems([f"{i+1}. {n}" for i, n in enumerate(self.STEPS)])
        self.step_list.setCurrentRow(0)
        # 点左边步骤可以任意跳转（以前点了没反应）
        self.step_list.currentRowChanged.connect(self._on_step_clicked)
        body.addWidget(self.step_list)
        # 右侧页面
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.stack.addWidget(self._page_basic())
        self.stack.addWidget(self._page_kind())
        self.stack.addWidget(self._page_portrait())
        # 叠到「立绘素材」页底部（a/b 两套立绘 + 表情增删）
        try:
            _pg = self.stack.widget(2)
            _inner = _pg.widget() if hasattr(_pg, "widget") else _pg
            _lay = _inner.layout() if _inner is not None else None
            if _lay is not None:
                _lay.addWidget(self._page_portrait_extras())
                print("[Wizard] 已在「立绘素材」页挂上 两套立绘 + 表情管理")
        except Exception as _e:
            print(f"[Wizard] ⚠ 挂载立绘扩展区失败: {_e}")
        self.stack.addWidget(self._page_live2d())
        self.stack.addWidget(self._page_display())
        self.stack.addWidget(self._page_touch())
        self.stack.addWidget(self._page_voice())
        self.stack.addWidget(self._page_persona())
        self.stack.addWidget(self._page_done())

        # 底部按钮
        bar = QHBoxLayout()
        self.hint = QLabel("")
        self.hint.setStyleSheet(f"color:{warn_text().name()};font-size:12px;")
        bar.addWidget(self.hint, 1)
        self.btn_prev = QPushButton("上一步")
        self.btn_prev.clicked.connect(lambda: self._goto(self.stack.currentIndex() - 1))
        self.btn_next = QPushButton("下一步")
        self.btn_next.clicked.connect(lambda: self._goto(self.stack.currentIndex() + 1))
        self.btn_finish = QPushButton("完成创建")
        self.btn_finish.clicked.connect(self._finish)
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.btn_next)
        bar.addWidget(self.btn_finish)
        root.addLayout(bar)

    def _step_enabled(self, idx: int) -> bool:
        """该步骤是否适用。

        - 编辑已有角色：按**角色实际有的素材**（有 fgimages → 有立绘步骤；有模型 → 有 Live2D 步骤）
        - 新建角色：按向导里选的形象类型
        这样「有 Live2D 但也有 2D 立绘」的角色不会再把 2D 步骤藏起来。"""
        need = self.STEP_ONLY.get(idx)
        if not need:
            return True
        try:
            if self.pet_id:
                from pets.pet_registry import get_fgimages_dir, get_live2d_model_json
                if need == "2d":
                    return bool(get_fgimages_dir(self.pet_id))
                return bool(get_live2d_model_json(self.pet_id))
        except Exception:
            pass
        return self._kind() == need

    def _on_step_clicked(self, idx: int):
        """点左边步骤列表 → 跳到该步（不适用的步骤自动落到最近的适用步）"""
        if idx < 0:
            return
        if getattr(self, "_in_goto", False):
            return
        self._goto(idx)

    def _goto(self, idx, _dir: int = 0):
        idx = max(0, min(self.stack.count() - 1, idx))
        if not self._step_enabled(idx):
            step = -1 if (_dir < 0 or idx < self.stack.currentIndex()) else 1
            nxt = idx + step
            if nxt < 0 or nxt > self.stack.count() - 1:
                return
            return self._goto(nxt, step)
        self._in_goto = True
        try:
            self.stack.setCurrentIndex(idx)
            self.step_list.setCurrentRow(idx)
            self.btn_prev.setEnabled(idx > 0)
            self.btn_next.setEnabled(idx < self.stack.count() - 1)
            self.btn_finish.setVisible(idx == self.stack.count() - 1)
            # 步骤内提示（哪几步对当前形象不适用）
            skip = [self.STEPS[i] for i in self.STEP_ONLY if not self._step_enabled(i)]
            self.hint.setText(("（本角色不需要：" + "、".join(skip) + "）") if skip else "")
            if idx == len(self.STEPS) - 1:
                self._refresh_summary()
            elif self.STEPS[idx] == "显示与对话框":
                if getattr(self, "_cur_disp_mode", None) is None:
                    self._cur_disp_mode = self._cur_mode()
                    self._bind_disp_widgets()
                self._refresh_display_preview()
        finally:
            self._in_goto = False

    # ── 步骤 1：基础信息 ──
    def _page_basic(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        grid = QGridLayout()
        self.ed_id = QLineEdit()
        self.ed_id.setPlaceholderText("英文/数字，作为文件夹名，如 murasame2")
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("显示名称，如 丛雨")
        self.ed_disp = QLineEdit()
        self.ed_disp.setPlaceholderText("（可选）更完整的显示名，如 丛雨ムラサメ")
        self.ed_intro = QLineEdit()
        self.ed_intro.setPlaceholderText("（可选）一句话简介")
        self.ed_avatar = QLineEdit()
        btn_av = QPushButton("选择…")
        btn_av.clicked.connect(self._pick_avatar)
        grid.addWidget(QLabel("桌宠 ID*"), 0, 0)
        grid.addWidget(self.ed_id, 0, 1)
        grid.addWidget(QLabel("名称*"), 1, 0)
        grid.addWidget(self.ed_name, 1, 1)
        grid.addWidget(QLabel("显示名"), 2, 0)
        grid.addWidget(self.ed_disp, 2, 1)
        grid.addWidget(QLabel("简介"), 3, 0)
        grid.addWidget(self.ed_intro, 3, 1)
        grid.addWidget(QLabel("头像"), 4, 0)
        grid.addWidget(self.ed_avatar, 4, 1)
        grid.addWidget(btn_av, 4, 2)
        lay.addLayout(grid)
        tip = QLabel("提示：ID 创建后不建议修改（它是角色包文件夹名）。\n"
                     "名称会用在对话里（AI 会知道「我叫这个名字」）。")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        lay.addWidget(tip)
        lay.addStretch()
        return w

    def _suggest_id(self):
        """名称是中文等情况自动给一个可用 ID（pet1、pet2…）"""
        try:
            from pets.pet_registry import get_pet_ids
            used = set(get_pet_ids())
        except Exception:
            used = set()
        for i in range(1, 200):
            cand = f"pet{i}"
            if cand not in used:
                return cand
        import time
        return f"pet{int(time.time()) % 100000}"

    def _pick_avatar(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择头像图片", "", "图片 (*.png *.jpg *.jpeg *.webp)")
        if p:
            self.ed_avatar.setText(p)

    # ── 步骤 2：形象类型 ──
    def _page_kind(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        box = QGroupBox("这个桌宠用哪种形象？")
        bl = QVBoxLayout(box)
        self.rb_2d = QRadioButton("2D 立绘（静态图片，按情绪换表情）")
        self.rb_l2d = QRadioButton("Live2D 模型（可动模型，长按 Shift 切换）")
        self.rb_2d.setChecked(True)
        bl.addWidget(self.rb_2d)
        bl.addWidget(self.rb_l2d)
        lay.addWidget(box)

        box2 = QGroupBox("选择 2D 立绘的制作方式")
        b2 = QVBoxLayout(box2)
        self.rb_single = QRadioButton("简单：每个表情一张整图（有多少表情就放几张图）")
        self.rb_layers = QRadioButton("进阶：多图层拼合（表情/服装/发型/装饰分别一张图，"
                                      "像丛雨那样拼成一张立绘）")
        self.rb_single.setChecked(True)
        b2.addWidget(self.rb_single)
        b2.addWidget(self.rb_layers)
        lay.addWidget(box2)
        tip = QLabel("· 简单方式：一张图 = 一个表情，最省事，适合自己画的单图立绘。\n"
                     "· 进阶方式：需要图层素材 + 图层索引 txt（和丛雨角色包同格式），"
                     "可以换衣服、换发型、叠装饰。\n"
                     "· 两种方式互不影响，之后在本向导「设置」里随时可以改。")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        lay.addWidget(tip)


        lay.addStretch()
        return w

    def _kind(self):
        return "live2d" if self.rb_l2d.isChecked() else "2d"

    # ── 步骤 3：立绘素材 ──
    def _page_portrait(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("图层前缀："))
        self.ed_prefix = QLineEdit()
        self.ed_prefix.setPlaceholderText("如 mypet（素材文件名会以它开头）")
        row.addWidget(self.ed_prefix, 1)
        lay.addLayout(row)

        # 简单方式：情绪 → 图片
        self.grp_single = QGroupBox("简单方式：每个表情一张图")
        sl = QVBoxLayout(self.grp_single)
        self._emo_rows = []
        self.emo_host = QWidget()
        self.emo_v = QVBoxLayout(self.emo_host)
        self.emo_v.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.emo_host)
        for e in EMOTION_PRESET:
            self._add_emotion_row(e)
        hb = QHBoxLayout()
        b_add = QPushButton("+ 添加表情")
        b_add.clicked.connect(lambda: self._add_emotion_row(""))
        hb.addWidget(b_add)
        hb.addStretch()
        sl.addLayout(hb)
        lay.addWidget(self.grp_single)

        # 进阶方式：图层目录 + 映射
        self.grp_layers = QGroupBox("进阶方式：多图层拼合")
        ll = QVBoxLayout(self.grp_layers)
        r2 = QHBoxLayout()
        self.ed_layer_dir = QLineEdit()
        self.ed_layer_dir.setPlaceholderText("图层素材所在文件夹（含 <前缀>a.txt 索引与图层 png）")
        b_dir = QPushButton("选择文件夹…")
        b_dir.clicked.connect(self._pick_layer_dir)
        b_read = QPushButton("读取图层")
        b_read.clicked.connect(self._load_layers)
        r2.addWidget(self.ed_layer_dir, 1)
        r2.addWidget(b_dir)
        r2.addWidget(b_read)
        ll.addLayout(r2)
        self.lbl_layers = QLabel("（选择文件夹后点「读取图层」，下面就能下拉选择每个部位用哪张图层）")
        self.lbl_layers.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        ll.addWidget(self.lbl_layers)

        g = QGridLayout()
        g.addWidget(QLabel("默认表情图层"), 0, 0)
        self.cb_emo_default = QComboBox()
        g.addWidget(self.cb_emo_default, 0, 1, 1, 3)
        row_i = 1
        self._emo_combos = {}
        for e in EMOTION_PRESET:
            g.addWidget(QLabel(f"「{e}」表情图层"), row_i, 0)
            cb = QComboBox()
            self._emo_combos[e] = cb
            g.addWidget(cb, row_i, 1, 1, 3)
            row_i += 1
        g.addWidget(QLabel("服装：名称 / 服装图层 / 发型图层"), row_i, 0)
        self.cloth_rows_host = QWidget()
        self.cloth_rows = QVBoxLayout(self.cloth_rows_host)
        self.cloth_rows.setContentsMargins(0, 0, 0, 0)
        b_cloth = QPushButton("+ 添加服装")
        b_cloth.clicked.connect(lambda: self._add_cloth_row("", "", ""))
        g.addWidget(self.cloth_rows_host, row_i, 1, 1, 2)
        g.addWidget(b_cloth, row_i, 3)
        row_i += 1
        g.addWidget(QLabel("装饰：名称 / 图层"), row_i, 0)
        self.decor_rows_host = QWidget()
        self.decor_rows = QVBoxLayout(self.decor_rows_host)
        self.decor_rows.setContentsMargins(0, 0, 0, 0)
        b_decor = QPushButton("+ 添加装饰")
        b_decor.clicked.connect(lambda: self._add_decor_row("", ""))
        g.addWidget(self.decor_rows_host, row_i, 1, 1, 2)
        g.addWidget(b_decor, row_i, 3)
        ll.addLayout(g)
        lay.addWidget(self.grp_layers)

        def _sync_single():
            show_s = self.rb_single.isChecked()
            self.grp_single.setVisible(show_s)
            self.grp_layers.setVisible(not show_s)
        self.rb_single.toggled.connect(_sync_single)
        _sync_single()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        return scroll

    def _add_emotion_row(self, name, path=""):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        ed = QLineEdit(name)
        ed.setPlaceholderText("表情名（如 高兴）")
        ed.setFixedWidth(110)
        le = QLineEdit(path)
        le.setPlaceholderText("图片文件")
        b = QPushButton("选择…")
        b.setFixedWidth(70)
        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(30)

        def pick():
            p, _ = QFileDialog.getOpenFileName(row, "选择立绘图片", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp)")
            if p:
                le.setText(p)
                if not ed.text().strip():
                    ed.setText(os.path.splitext(os.path.basename(p))[0])
        b.clicked.connect(pick)

        def remove():
            self.emo_v.removeWidget(row)
            row.deleteLater()
            self._emo_rows = [r for r in self._emo_rows if r[0] is not row]
        del_btn.clicked.connect(remove)
        h.addWidget(ed)
        h.addWidget(le, 1)
        h.addWidget(b)
        h.addWidget(del_btn)
        self.emo_v.addWidget(row)
        self._emo_rows.append((row, ed, le))

    def _pick_layer_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图层素材文件夹")
        if d:
            self.ed_layer_dir.setText(d)
            self._load_layers()

    def _load_layers(self):
        d = self.ed_layer_dir.text().strip()
        idxs = find_index_files(d)
        if not idxs:
            self.lbl_layers.setText("❌ 这个文件夹里没找到图层索引 txt（应形如 <前缀>a.txt）")
            return
        idx = idxs[0]
        layers = parse_layer_index(idx)
        self._layers = layers
        if not layers:
            self.lbl_layers.setText(f"❌ 索引读取失败或没有图层：{os.path.basename(idx)}")
            return
        base = os.path.basename(idx)
        if not self.ed_prefix.text().strip():
            self.ed_prefix.setText(base[:-5] if base.endswith("a.txt") else os.path.splitext(base)[0])
        self.lbl_layers.setText(f"✅ {base}：共 {len(layers)} 个图层")
        names = [f"{l['name']}（ID {l['id']}）" for l in layers]
        for cb in [self.cb_emo_default] + list(self._emo_combos.values()):
            cb.clear()
            cb.addItem("（不使用）", 0)
            for l, label in zip(layers, names):
                cb.addItem(label, l["id"])
        for rows, n in ((self.cloth_rows, 3), (self.decor_rows, 2)):
            for i in range(rows.count()):
                holder = rows.itemAt(i).widget()
                if holder is None:
                    continue
                combos = holder.findChildren(QComboBox)
                for cb in combos:
                    cb.clear()
                    cb.addItem("（不使用）", 0)
                    for l, label in zip(layers, names):
                        cb.addItem(label, l["id"])
        if not self._cloth_added:
            self._cloth_added = True
            self._add_cloth_row("默认", "", "")

    def _page_portrait_extras(self):
        """「立绘素材」页底部追加的两块：a/b 两套立绘声明 + 表情增删。
        由 _build() 在页面创建后显式挂上（避免插错页）。"""
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        # ── a / b 两套立绘（a 侧面 / b 正面）：按需求放在「立绘素材」页 ──
        self.gb_sets_here = QGroupBox("立绘套数（a = 侧面立绘，b = 正面立绘）")
        _gsh = QVBoxLayout(self.gb_sets_here)
        self.chk_two_sets_here = QCheckBox("本角色有两套立绘（a 侧面 / b 正面）")
        self.chk_two_sets_here.toggled.connect(self._on_two_sets_toggled_here)
        _gsh.addWidget(self.chk_two_sets_here)
        self.cmb_preview_set_here = QComboBox()
        self.cmb_preview_set_here.addItem("预览 a 套（侧面）", "a")
        self.cmb_preview_set_here.addItem("预览 b 套（正面）", "b")
        self.cmb_preview_set_here.currentIndexChanged.connect(self._on_preview_set_here)
        _gsh.addWidget(self.cmb_preview_set_here)
        _ghint = QLabel("没有两套素材的角色不会出现这个选项，也不会有 a/b 切换。")
        _ghint.setStyleSheet(f"color:{Gray2.name()};font-size:11px;")
        _gsh.addWidget(_ghint)
        lay.addWidget(self.gb_sets_here)

# ── 表情增删（立绘栏）：单图角色增删图片；图层角色列出可停用 ──
        self.gb_emo_portrait = QGroupBox("表情管理（添加 / 删除）")
        _gpe = QVBoxLayout(self.gb_emo_portrait)
        self.emo_portrait_host = QWidget()
        self.emo_portrait_layout = QVBoxLayout(self.emo_portrait_host)
        self.emo_portrait_layout.setContentsMargins(0, 0, 0, 0)
        _gpe.addWidget(self.emo_portrait_host)
        _pr = QHBoxLayout()
        _b1 = QPushButton("➕ 添加表情")
        _b1.clicked.connect(lambda: self._emo_edit_add())
        _b2 = QPushButton("🔄 读取现有表情")
        _b2.clicked.connect(self._emo_edit_load)
        _pr.addWidget(_b1); _pr.addWidget(_b2); _pr.addStretch()
        _gpe.addLayout(_pr)
        lay.addWidget(self.gb_emo_portrait)
        return host

    def _add_cloth_row(self, name, cloth, hair):
        holder = QWidget()
        h = QHBoxLayout(holder)
        h.setContentsMargins(0, 0, 0, 0)
        ed = QLineEdit(name)
        ed.setPlaceholderText("服装名")
        ed.setFixedWidth(90)
        cb1 = QComboBox()
        cb2 = QComboBox()
        for cb in (cb1, cb2):
            cb.addItem("（不使用）", 0)
            for l in getattr(self, "_layers", []):
                cb.addItem(f"{l['name']}（ID {l['id']}）", l["id"])
        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(30)

        def remove():
            self.cloth_rows.removeWidget(holder)
            holder.deleteLater()
        del_btn.clicked.connect(remove)
        h.addWidget(ed)
        h.addWidget(cb1)
        h.addWidget(cb2)
        h.addWidget(del_btn)
        self.cloth_rows.addWidget(holder)

    def _add_decor_row(self, name, layer):
        holder = QWidget()
        h = QHBoxLayout(holder)
        h.setContentsMargins(0, 0, 0, 0)
        ed = QLineEdit(name)
        ed.setPlaceholderText("装饰名")
        ed.setFixedWidth(90)
        cb = QComboBox()
        cb.addItem("（不使用）", 0)
        for l in getattr(self, "_layers", []):
            cb.addItem(f"{l['name']}（ID {l['id']}）", l["id"])
        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(30)

        def remove():
            self.decor_rows.removeWidget(holder)
            holder.deleteLater()
        del_btn.clicked.connect(remove)
        h.addWidget(ed)
        h.addWidget(cb)
        h.addWidget(del_btn)
        self.decor_rows.addWidget(holder)

    # ── 步骤 4：Live2D ──
    def _page_live2d(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("选择 Live2D 模型文件（*.model3.json）："))
        row = QHBoxLayout()
        self.ed_l2d = QLineEdit()
        self.ed_l2d.setPlaceholderText("如 D:/models/xxx/xxx.model3.json")
        b = QPushButton("选择模型…")
        b.clicked.connect(self._pick_l2d)
        row.addWidget(self.ed_l2d, 1)
        row.addWidget(b)
        lay.addLayout(row)
        tip = QLabel("· 选中的模型会连同同目录/子目录的贴图、动作、表情一起复制进角色包 live2d/；\n"
                     "· 桌宠运行时「长按 Shift 2 秒」可在 2D 立绘与 Live2D 之间切换；\n"
                     "· 需要安装 live2d-py 与 PyOpenGL 依赖（启动器首次启动会提示）。")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        lay.addWidget(tip)
        lay.addStretch()
        return w

    def _pick_l2d(self):
        p, _ = QFileDialog.getOpenFileName(self, "选择 Live2D 模型", "", "Live2D 模型 (*.model3.json)")
        if p:
            self.ed_l2d.setText(p)

    # ── 步骤 5：显示与对话框（2D / Live2D 完全独立 + 拼合立绘预览与位置微调）──
    def _page_display(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)

        # ① 显示方式（2D 立绘 / Live2D 模型）
        top = QHBoxLayout()
        self.rb_disp_2d = QRadioButton("🖼 2D 立绘显示")
        self.rb_disp_lv = QRadioButton("🎭 Live2D 模型显示")
        self._disp_group = QButtonGroup(self)
        self._disp_group.addButton(self.rb_disp_2d, 0)
        self._disp_group.addButton(self.rb_disp_lv, 1)
        self.rb_disp_2d.toggled.connect(lambda on: on and self._on_disp_mode_changed("2d"))
        self.rb_disp_lv.toggled.connect(lambda on: on and self._on_disp_mode_changed("live2d"))
        top.addWidget(QLabel("桌宠显示方式："))
        top.addWidget(self.rb_disp_2d)
        top.addWidget(self.rb_disp_lv)
        top.addStretch()
        self.btn_open_studio = QPushButton("🎨 打开立绘工坊（换装 / 表情）")
        self.btn_open_studio.clicked.connect(self._open_studio)
        top.addWidget(self.btn_open_studio)
        lay.addLayout(top)

        self.lbl_disp_tip = QLabel("")
        self.lbl_disp_tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        self.lbl_disp_tip.setWordWrap(True)
        lay.addWidget(self.lbl_disp_tip)

        row = QHBoxLayout()
        self.disp_preview = DisplayPreview(self)
        self.disp_preview.setMinimumSize(360, 280)
        row.addWidget(self.disp_preview, 1)

        col = QVBoxLayout()
        self.disp_stack = QStackedWidget()

        # ── 2D 面板 ──
        p2d = QWidget()
        l2 = QVBoxLayout(p2d)
        l2.setContentsMargins(0, 0, 0, 0)
        self.gb_sets = QGroupBox("立绘套数（a = 侧面立绘，b = 正面立绘）")
        gs = QVBoxLayout(self.gb_sets)
        self.chk_two_sets = QCheckBox("本角色有两套立绘（a 侧面 / b 正面）")
        self.chk_two_sets.toggled.connect(self._on_two_sets_toggled)
        gs.addWidget(self.chk_two_sets)
        self.cmb_preview_set = QComboBox()
        self.cmb_preview_set.addItem("预览 a 套（侧面）", "a")
        self.cmb_preview_set.addItem("预览 b 套（正面）", "b")
        self.cmb_preview_set.currentIndexChanged.connect(self._on_preview_set_changed)
        gs.addWidget(self.cmb_preview_set)
        l2.addWidget(self.gb_sets)

        self.gb_size2d = QGroupBox("立绘大小与位置（多图拼合的立绘也按此显示）")
        gz = QVBoxLayout(self.gb_size2d)
        self.sld_height = QSlider(Qt.Horizontal); self.sld_height.setRange(10, 95)
        self.sld_scale = QSlider(Qt.Horizontal); self.sld_scale.setRange(30, 200)
        self.spin_offx = QSpinBox(); self.spin_offx.setRange(-800, 800)
        self.spin_offy = QSpinBox(); self.spin_offy.setRange(-800, 800)
        for lab, wid in (("占屏高度", self.sld_height), ("整体缩放", self.sld_scale),
                         ("水平偏移", self.spin_offx), ("垂直偏移", self.spin_offy)):
            rr = QHBoxLayout()
            rr.addWidget(QLabel(lab)); rr.addWidget(wid, 1)
            gz.addLayout(rr)
        self.sld_height.valueChanged.connect(self._on_display_slider)
        self.sld_scale.valueChanged.connect(self._on_display_slider)
        self.spin_offx.valueChanged.connect(self._on_display_slider)
        self.spin_offy.valueChanged.connect(self._on_display_slider)
        l2.addWidget(self.gb_size2d)

        self.gb_wiz_cloth = QGroupBox("服装（选一件 + 微调位置，防穿模）")
        gcl = QVBoxLayout(self.gb_wiz_cloth)
        self.cmb_wiz_cloth = QComboBox()
        self.cmb_wiz_cloth.currentIndexChanged.connect(self._on_wiz_cloth_changed)
        gcl.addWidget(self.cmb_wiz_cloth)
        self.btn_cloth_tune = QPushButton("👗 服装位置 / 大小微调…")
        self.btn_cloth_tune.clicked.connect(self._open_layer_tune)
        gcl.addWidget(self.btn_cloth_tune)
        l2.addWidget(self.gb_wiz_cloth)

        self.btn_layer_tune = QPushButton("🧩 表情 / 装饰 / 基础 位置微调…")
        self.btn_layer_tune.clicked.connect(self._open_layer_tune)
        l2.addWidget(self.btn_layer_tune)

        # 单图角色的「表情」管理：能加也能删（以前需要在「立绘素材」步骤里操作，不好找）
        self.gb_emo = QGroupBox("表情（每个表情一张整图 · 可增删）")
        ge = QVBoxLayout(self.gb_emo)
        self.emo_edit_host = QWidget()
        self.emo_edit_layout = QVBoxLayout(self.emo_edit_host)
        self.emo_edit_layout.setContentsMargins(0, 0, 0, 0)
        ge.addWidget(self.emo_edit_host)
        brow = QHBoxLayout()
        self.btn_emo_add = QPushButton("➕ 添加表情")
        self.btn_emo_add.clicked.connect(self._emo_edit_add)
        self.btn_emo_reload = QPushButton("🔄 读取现有表情")
        self.btn_emo_reload.clicked.connect(self._emo_edit_load)
        brow.addWidget(self.btn_emo_add); brow.addWidget(self.btn_emo_reload)
        brow.addStretch()
        ge.addLayout(brow)
        l2.addWidget(self.gb_emo)
        l2.addStretch()
        self.disp_stack.addWidget(p2d)

        # ── Live2D 面板 ──
        plv = QWidget()
        llv = QVBoxLayout(plv)
        llv.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("Live2D 大小与位置（与 2D 立绘完全独立）")
        gl = QVBoxLayout(gb)
        self.sld_lv_h = QSlider(Qt.Horizontal); self.sld_lv_h.setRange(15, 95)
        self.sld_lv_w = QSlider(Qt.Horizontal); self.sld_lv_w.setRange(20, 200)
        self.sld_lv_scale = QSlider(Qt.Horizontal); self.sld_lv_scale.setRange(30, 250)
        self.spin_lv_ox = QSpinBox(); self.spin_lv_ox.setRange(-800, 800)
        self.spin_lv_oy = QSpinBox(); self.spin_lv_oy.setRange(-800, 800)
        for lab, wid in (("占屏高度", self.sld_lv_h), ("宽高比 ×100", self.sld_lv_w),
                         ("模型缩放", self.sld_lv_scale),
                         ("水平偏移", self.spin_lv_ox), ("垂直偏移", self.spin_lv_oy)):
            rr = QHBoxLayout()
            rr.addWidget(QLabel(lab)); rr.addWidget(wid, 1)
            gl.addLayout(rr)
        for wid in (self.sld_lv_h, self.sld_lv_w, self.sld_lv_scale,
                    self.spin_lv_ox, self.spin_lv_oy):
            try:
                wid.valueChanged.connect(self._on_display_slider)
            except Exception:
                pass
        llv.addWidget(gb)
        self.lbl_lv_info = QLabel("")
        self.lbl_lv_info.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        self.lbl_lv_info.setWordWrap(True)
        llv.addWidget(self.lbl_lv_info)
        self.btn_l2d_win = QPushButton("🎭 打开 Live2D 实时预览窗口")
        self.btn_l2d_win.setMinimumHeight(36)
        self.btn_l2d_win.clicked.connect(self._open_l2d_window)
        llv.addWidget(self.btn_l2d_win)
        llv.addWidget(QLabel("提示：预览窗口是独立的不透明窗口（透明窗口里 OpenGL 画不出来，"
                             "旧版启动器也是这么显示的）。"))
        llv.addStretch()
        self.disp_stack.addWidget(plv)

        col.addWidget(self.disp_stack)

        self.gb_box = QGroupBox("对话框区域与字号（2D / Live2D 各存一份，互不影响）")
        gb2 = QVBoxLayout(self.gb_box)
        grid = QGridLayout()
        for i, (name, bx, by) in enumerate([
                ("左上", 0.03, 0.03), ("上中", 0.30, 0.03), ("右上", 0.57, 0.03),
                ("左中", 0.03, 0.32), ("居中", 0.30, 0.32), ("右中", 0.57, 0.32),
                ("左下", 0.03, 0.62), ("下中", 0.30, 0.62), ("右下", 0.57, 0.62)]):
            b = QPushButton(name)
            b.setFixedHeight(24)
            b.clicked.connect(lambda _=False, x=bx, y=by: self._set_text_box_pos(x, y))
            grid.addWidget(b, i // 3, i % 3)
        gb2.addLayout(grid)
        self.sld_box_w = QSlider(Qt.Horizontal); self.sld_box_w.setRange(30, 100)
        self.sld_box_h = QSlider(Qt.Horizontal); self.sld_box_h.setRange(8, 70)
        self.sld_font = QSlider(Qt.Horizontal); self.sld_font.setRange(50, 250)
        self.lbl_font_px = QLabel("")
        self.lbl_font_px.setStyleSheet(f"color:{Gray2.name()};font-size:11px;")
        for lab, wid in (("对话框宽度", self.sld_box_w), ("对话框高度", self.sld_box_h),
                         ("字号", self.sld_font)):
            rr = QHBoxLayout()
            rr.addWidget(QLabel(lab)); rr.addWidget(wid, 1)
            gb2.addLayout(rr)
        gb2.addWidget(self.lbl_font_px)
        for wid in (self.sld_box_w, self.sld_box_h, self.sld_font):
            wid.valueChanged.connect(self._on_display_slider)
        col.addWidget(self.gb_box)
        _rb = QPushButton("♻ 恢复默认（当前显示方式）")
        _rb.setToolTip("把当前显示方式（2D 或 Live2D）的大小、位置、对话框区域、字号恢复默认")
        _rb.clicked.connect(self._reset_display_defaults)
        col.addWidget(_rb)
        col.addStretch()
        row.addLayout(col)
        lay.addLayout(row, 1)
        return w

    # ── 显示设置的数据层：2D / Live2D 各一套 ──
    def _disp_defaults(self) -> dict:
        return {
            "2d": {"height_ratio": 0.55, "scale": 1.0, "offset_x": 0, "offset_y": 0,
                   "text_box": [0.06, 0.05, 0.88, 0.38], "font_scale": 1.0,
                   "sets": ["a"], "preview_set": "a"},
            "live2d": {"height_ratio": 0.85, "width_ratio": 0.67, "scale": 1.0,
                       "offset_x": 0, "offset_y": 0,
                       "text_box": [0.10, 0.55, 0.80, 0.38], "font_scale": 1.0},
        }

    def _cur_mode(self) -> str:
        try:
            return "live2d" if self.rb_disp_lv.isChecked() else "2d"
        except Exception:
            return "2d"

    def _disp(self) -> dict:
        if not hasattr(self, "_disp_data"):
            self._disp_data = self._disp_defaults()
        return self._disp_data

    def _display_values(self) -> dict:
        return dict(self._disp().get(self._cur_mode(), {}))

    def _bind_disp_widgets(self):
        """把当前显示方式的数值灌进控件（切模式时调用；屏蔽信号以免误写盘）"""
        d = self._display_values()
        mode = self._cur_mode()
        wid = [self.sld_height, self.sld_scale, self.spin_offx, self.spin_offy,
               self.sld_lv_h, self.sld_lv_w, self.sld_lv_scale, self.spin_lv_ox,
               self.spin_lv_oy, self.sld_box_w, self.sld_box_h, self.sld_font]
        for x in wid:
            try:
                x.blockSignals(True)
            except Exception:
                pass
        tb = d.get("text_box") or [0.06, 0.05, 0.88, 0.38]
        try:
            if mode == "2d":
                self.sld_height.setValue(int(float(d.get("height_ratio", 0.55)) * 100))
                self.sld_scale.setValue(int(float(d.get("scale", 1.0)) * 100))
                self.spin_offx.setValue(int(d.get("offset_x", 0)))
                self.spin_offy.setValue(int(d.get("offset_y", 0)))
            else:
                self.sld_lv_h.setValue(int(float(d.get("height_ratio", 0.85)) * 100))
                self.sld_lv_w.setValue(int(float(d.get("width_ratio", 0.67)) * 100))
                self.sld_lv_scale.setValue(int(float(d.get("scale", 1.0)) * 100))
                self.spin_lv_ox.setValue(int(d.get("offset_x", 0)))
                self.spin_lv_oy.setValue(int(d.get("offset_y", 0)))
            self.sld_box_w.setValue(int(float(tb[2]) * 100))
            self.sld_box_h.setValue(int(float(tb[3]) * 100))
            self.sld_font.setValue(int(float(d.get("font_scale", 1.0)) * 100))
        except Exception as e:
            print(f"[Wizard] ⚠ 绑定显示控件失败: {e}")
        for x in wid:
            try:
                x.blockSignals(False)
            except Exception:
                pass
        self.disp_preview.set_box(float(tb[0]), float(tb[1]), float(tb[2]), float(tb[3]))
        self._update_font_px_label()

    def _reset_display_defaults(self):
        """把当前显示方式的设置恢复默认（不影响另一种显示方式）"""
        try:
            mode = self._cur_mode()
            self._disp()[mode] = dict(self._disp_defaults()[mode])
            self._bind_disp_widgets()
            self._refresh_display_preview()
            self.hint.setText(f"已把「{'2D 立绘' if mode == '2d' else 'Live2D'}」的设置恢复默认")
            print(f"[Wizard] 显示设置已恢复默认: {mode}")
        except Exception as e:
            print(f"[Wizard] ⚠ 恢复默认失败: {e}")

    def _write_back_disp(self, mode=None):
        """把控件值写回指定模式（默认当前模式）。切模式时必须显式传旧模式，
        否则会拿「新模式的界面」去写「旧模式的数据」→ 数值被写坏。"""
        mode = mode or self._cur_mode()
        d = self._disp().setdefault(mode, {})
        try:
            if mode == "2d":
                d["height_ratio"] = round(self.sld_height.value() / 100.0, 3)
                d["scale"] = round(self.sld_scale.value() / 100.0, 3)
                d["offset_x"] = int(self.spin_offx.value())
                d["offset_y"] = int(self.spin_offy.value())
            else:
                d["height_ratio"] = round(self.sld_lv_h.value() / 100.0, 3)
                d["width_ratio"] = round(self.sld_lv_w.value() / 100.0, 3)
                d["scale"] = round(self.sld_lv_scale.value() / 100.0, 3)
                d["offset_x"] = int(self.spin_lv_ox.value())
                d["offset_y"] = int(self.spin_lv_oy.value())
            d["text_box"] = [round(self.disp_preview.bx, 3), round(self.disp_preview.by, 3),
                             round(self.sld_box_w.value() / 100.0, 3),
                             round(self.sld_box_h.value() / 100.0, 3)]
            d["font_scale"] = round(self.sld_font.value() / 100.0, 2)
        except Exception as e:
            print(f"[Wizard] ⚠ 保存显示设置失败: {e}")

    def _on_disp_mode_changed(self, mode: str):
        try:
            prev = getattr(self, "_cur_disp_mode", None)
            if prev and prev != mode:
                self._write_back_disp(prev)     # ← 按旧模式写回（关键）
            self._cur_disp_mode = mode
            self.disp_stack.setCurrentIndex(0 if mode == "2d" else 1)
            self._bind_disp_widgets()
            self._refresh_display_preview()
            # 不再自动弹 Live2D 预览窗口（只在用户点按钮时才开 → 避免突然冒出个窗口）
        except Exception as e:
            print(f"[Wizard] ⚠ 切换显示方式失败: {e}")

    def _on_two_sets_toggled_here(self, on: bool):
        self._on_two_sets_toggled(on)

    def _on_preview_set_here(self, *_):
        try:
            d = self._disp().setdefault("2d", {})
            d["preview_set"] = str(self.cmb_preview_set_here.currentData() or "a")
        except Exception:
            pass
        self._refresh_display_preview()

    def _on_two_sets_toggled(self, on: bool):
        d = self._disp().setdefault("2d", {})
        d["sets"] = ["a", "b"] if on else ["a"]
        try:
            self.cmb_preview_set.setEnabled(bool(on))
        except Exception:
            pass
        self._refresh_display_preview()

    def _on_preview_set_changed(self, *_):
        d = self._disp().setdefault("2d", {})
        try:
            d["preview_set"] = str(self.cmb_preview_set.currentData() or "a")
        except Exception:
            d["preview_set"] = "a"
        self._refresh_display_preview()

    def _on_display_slider(self, *_):
        self._write_back_disp()
        self._update_font_px_label()
        # 几何类调节 60ms 防抖（拖动更顺；不重新合成，只重画预览）
        self._prev_deb = getattr(self, "_prev_deb", None)
        if self._prev_deb is None:
            self._prev_deb = QTimer(self)
            self._prev_deb.setSingleShot(True)
            self._prev_deb.timeout.connect(self._refresh_display_preview)
        self._prev_deb.start(60)

    def _update_font_px_label(self):
        """字号滑块旁边显示「实际字号」估算值（桌宠按对话框宽度算字号：
        宽度 × 0.0295 × 字号系数）"""
        try:
            from PyQt5.QtWidgets import QApplication
            scr = (self.screen() or QApplication.primaryScreen())
            scr_h = scr.availableGeometry().height() if scr else 900
            win_h = max(80, int(scr_h * (self.sld_height.value() / 100.0)))
            pix = getattr(self.disp_preview, "pix", None)
            ratio = 0.55
            if pix is not None and not pix.isNull() and pix.height() > 0:
                ratio = pix.width() / float(pix.height())
            area_w = max(40, int(max(60, int(win_h * ratio)) * self.sld_box_w.value() / 100.0))
            fs = self.sld_font.value() / 100.0
            px = max(9, int(round(area_w * 0.0295 * fs)))
            self.lbl_font_px.setText(
                f"实际字号 ≈ {px}px（桌宠按对话框宽度自动换算；此角色约 {area_w}px 宽）")
        except Exception as e:
            print(f"[Wizard] ⚠ 计算字号失败: {e}")

    def _set_text_box_pos(self, x: float, y: float):
        self.disp_preview.set_box(x, y, self.disp_preview.bw, self.disp_preview.bh)
        self._write_back_disp()
        self._refresh_display_preview()

    def _open_l2d_window(self):
        """打开角色的 Live2D 实时预览窗口"""
        try:
            from .live2d_preview import open_live2d_window
            from pets.pet_registry import get_live2d_model_json
            mj = get_live2d_model_json(self.pet_id) if self.pet_id else ""
            if not mj:
                self.hint.setText("⚠ 该角色没有可用的 Live2D 模型文件")
                return
            w = open_live2d_window(mj, None, pet_id=self.pet_id or None)
            self.hint.setText("🎭 已在新窗口打开 Live2D 实时预览" if w else "⚠ 打开失败（看日志）")
        except Exception as e:
            self.hint.setText(f"⚠ 打开失败：{e}")

    def _open_studio(self):
        """打开立绘工坊（换装 / 表情 / Live2D 预览）

        ⚠ 以前挂在「当前激活窗口」上并把它当父窗口 → 会开出第二个工坊、还可能被
        向导盖住，而且没带角色 ID（编辑新角色时预览的是活动角色）。现在统一挂到
        启动器外壳上、按本向导的角色打开（与桌宠目录里的「立绘工坊」同一套逻辑）。
        """
        try:
            from .portrait_studio import PortraitStudio
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import Qt as _Qt
            win = None
            try:
                for w in QApplication.topLevelWidgets():
                    if getattr(w, "_page_factories", None) or hasattr(w, "stack"):
                        win = w
                        break
            except Exception:
                win = None
            if win is None:
                win = self.window()
            pid = getattr(self, "pet_id", None)
            st = getattr(win, "_portrait_studio", None)
            try:
                if st is not None:
                    st.isHidden()          # C++ 对象是否还活着
            except Exception:
                st = None
            if st is None:
                st = PortraitStudio(None, pet_id=pid)
                try:
                    st.setWindowFlag(_Qt.Window, True)
                    st.setWindowFlag(_Qt.WindowStaysOnTopHint, True)
                except Exception:
                    pass
                try:
                    win._portrait_studio = st
                except Exception:
                    pass
            else:
                try:
                    st.reload_for_pet(pid)      # 换角色必须重载素材（否则显示上一个角色的立绘）
                except Exception:
                    try:
                        st._pet_id = pid
                        st._loaded_pet = None
                    except Exception:
                        pass
            st.show(); st.raise_(); st.activateWindow()
            try:
                from PyQt5.QtCore import QTimer as _QT
                _QT.singleShot(160, lambda: (st.raise_(), st.activateWindow()))
            except Exception:
                pass
            if not pid:
                try:
                    st.status_lbl.setText(
                        "ℹ 这是「新建中」的角色：先走到最后一步点完成，再回来调它的立绘。\n"
                        "（现在预览的是当前活动角色）")
                except Exception:
                    pass
        except Exception as e:
            print(f"[Wizard] ⚠ 打开立绘工坊失败: {e}")

    def _emo_edit_row(self, name: str, path: str):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        ed = QLineEdit(name)
        ed.setPlaceholderText("表情名")
        ed.setFixedWidth(90)
        le = QLineEdit(path)
        le.setPlaceholderText("图片文件")
        pb = QPushButton("选择…")
        pb.setFixedWidth(60)
        db = QPushButton("✕")
        db.setFixedWidth(28)
        db.setToolTip("删除这个表情")

        def _pick():
            f, _ = QFileDialog.getOpenFileName(row, "选择立绘图片", "",
                                              "图片 (*.png *.jpg *.jpeg *.webp *.bmp)")
            if f:
                le.setText(f)
                if not ed.text().strip():
                    ed.setText(os.path.splitext(os.path.basename(f))[0])
        pb.clicked.connect(_pick)

        def _del():
            self.emo_edit_layout.removeWidget(row)
            row.deleteLater()
            self._emo_edit_rows = [r for r in getattr(self, "_emo_edit_rows", [])
                                   if r[0] is not row]
            self._refresh_display_preview()
        db.clicked.connect(_del)
        h.addWidget(ed); h.addWidget(le, 1); h.addWidget(pb); h.addWidget(db)
        self.emo_edit_layout.addWidget(row)
        self._emo_edit_rows = getattr(self, "_emo_edit_rows", []) + [(row, ed, le)]

    def _emo_edit_add(self):
        self._emo_edit_row("", "")

    def _emo_edit_load(self):
        """把当前角色的表情读进列表（编辑已有角色）；没有就从立绘素材步骤里搬"""
        try:
            for row, _e, _l in list(getattr(self, "_emo_edit_rows", [])):
                self.emo_edit_layout.removeWidget(row)
                row.deleteLater()
            self._emo_edit_rows = []
        except Exception:
            self._emo_edit_rows = []
        _seen = set()
        # 先在「立绘素材」步骤里填过的（新建流程）
        try:
            for _row, ed, le in getattr(self, "_emo_rows", []):
                n = ed.text().strip()
                if (n or le.text().strip()) and n not in _seen:
                    _seen.add(n)
                    self._emo_edit_row(n, le.text().strip())
        except Exception:
            pass
        # 已有角色：从 pet.json 的 portrait 读出表情 → 素材里的图片
        try:
            from pets.pet_registry import (get_fgimages_dir, get_fgimages_prefix,
                                           get_portrait_emotions)
            d = get_fgimages_dir(self.pet_id) if self.pet_id else ""
            if d:
                pref = get_fgimages_prefix(self.pet_id)
                set_name = str(self._disp().get("2d", {}).get("preview_set") or "a")
                for emo, lid in (get_portrait_emotions(self.pet_id) or {}).items():
                    if str(emo) in _seen:
                        continue
                    p = os.path.join(d, f"{pref}{set_name}_{lid}.png")
                    if os.path.exists(p):
                        _seen.add(str(emo))
                        self._emo_edit_row(str(emo), p)
        except Exception as e:
            print(f"[Wizard] ⚠ 读取现有表情失败: {e}")
        self._refresh_display_preview()

    def _emo_edit_values(self) -> dict:
        out = {}
        for _row, ed, le in getattr(self, "_emo_edit_rows", []):
            n = ed.text().strip()
            p = le.text().strip()
            if n and p and os.path.exists(p):
                out[n] = p
        return out

    def _open_layer_tune(self):
        """图层位置微调（服装 / 表情 / 装饰 / 头发 / 基础人物）——防穿模"""
        try:
            dlg = _LayerTuneDialog(self, self._disp(), self._preview_image)
            dlg.exec_()
            # 新角色还没落盘 → 把待应用的微调留在向导里，创建时一起写入
            try:
                self._pending_layer_adjust = dlg._collect_table()
            except Exception:
                pass
            self._refresh_display_preview()
        except Exception as e:
            print(f"[Wizard] ⚠ 打开图层微调失败: {e}")

    def _cloth_options(self) -> list:
        """该角色的服装（有服装才显示；单图 / 纯 Live2D 角色为空）"""
        if getattr(self, "_cloth_cache", None) is not None:
            return self._cloth_cache
        out = []
        try:
            # 纯 Live2D 角色（没有 2D 立绘素材）没有服装可换 → 直接返回空
            try:
                from pets.pet_registry import get_fgimages_dir
                if self.pet_id and not get_fgimages_dir(self.pet_id):
                    self._cloth_cache = []
                    return []
            except Exception:
                pass
            if self.pet_id:
                from .portrait_studio import PortraitStudio
                data, _err = PortraitStudio._run_cli(["list"], timeout=60, pet_id=self.pet_id)
                d = json.loads(data.splitlines()[-1]) if data else {}
                if str(d.get("mode") or "layers") == "layers":
                    sets = d.get("sets") or ["a"]
                    act = str(d.get("active") or sets[0])
                    if act not in sets:
                        act = sets[0]
                    out = [(str(x[0]), int(x[1]), int(x[2]))
                           for x in ((d.get("clothes") or {}).get(act) or [])]
        except Exception as e:
            print(f"[Wizard] ⚠ 枚举服装失败: {e}")
        self._cloth_cache = out
        return out

    def _on_wiz_cloth_changed(self, *_):
        """换默认服装：写进「立绘工坊」共用装扮（桌宠 / QQ 立绘同时生效）"""
        try:
            d = self.cmb_wiz_cloth.currentData()
            if not d or not self.pet_id:
                return
            name = d[0]
            def _work():
                from .portrait_studio import PortraitStudio
                out, err = PortraitStudio._run_cli(["save", "a", name, ""], timeout=60,
                                                  pet_id=self.pet_id)
                print(f"[Wizard] 默认服装 → {name}: {(out or err)[:80]}")
            import threading
            threading.Thread(target=_work, daemon=True).start()
            self._cloth_cache = None
            QTimer.singleShot(1500, self._refresh_display_preview)
            self.hint.setText(f"已选择默认服装：{name}（立绘工坊同步）")
        except Exception as e:
            print(f"[Wizard] ⚠ 保存默认服装失败: {e}")

    def _ensure_two_sets_state(self):
        """自动检测角色有几套立绘：只有两套才给 a/b 的调节与切换入口"""
        try:
            from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
            d = get_fgimages_dir(self.pet_id) if self.pet_id else ""
            sets = []
            if d:
                pref = get_fgimages_prefix(self.pet_id)
                sets = sorted({f[len(pref):-4] for f in os.listdir(d)
                               if f.startswith(pref) and f.endswith(".txt")})
            two = ("a" in sets and "b" in sets)
            self.chk_two_sets.blockSignals(True)
            self.chk_two_sets.setChecked(two)
            self.chk_two_sets.setEnabled(bool(sets))
            self.chk_two_sets.blockSignals(False)
            self.cmb_preview_set.setEnabled(two)
            self.gb_sets.setVisible(False)          # 已挪到「立绘素材」页
            try:
                self.gb_sets_here.setVisible(bool(sets))
                self.chk_two_sets_here.blockSignals(True)
                self.chk_two_sets_here.setChecked(two)
                self.chk_two_sets_here.setEnabled(bool(sets))
                self.chk_two_sets_here.blockSignals(False)
                self.cmb_preview_set_here.setEnabled(two)
                _ps = str(self._disp().get("2d", {}).get("preview_set") or "a")
                for _i in range(self.cmb_preview_set_here.count()):
                    if self.cmb_preview_set_here.itemData(_i) == _ps:
                        self.cmb_preview_set_here.blockSignals(True)
                        self.cmb_preview_set_here.setCurrentIndex(_i)
                        self.cmb_preview_set_here.blockSignals(False)
                        break
            except Exception as _e:
                print(f"[Wizard] ⚠ 立绘页两套配置同步失败: {_e}")
            self._disp().setdefault("2d", {})["sets"] = ["a", "b"] if two else ["a"]
            print(f"[Wizard] 立绘套数检测: {sets or '（无）'} → 两套={two}")
        except Exception as e:
            print(f"[Wizard] ⚠ 检测立绘套数失败: {e}")

    def _preview_image(self) -> QPixmap:
        """预览立绘：拼合立绘走 runtime venv 真实合成（含待应用的图层微调）"""
        try:
            mode = self._collect().get("portrait_mode")
        except Exception:
            mode = "single"
        set_name = str(self._disp().get("2d", {}).get("preview_set") or "a")
        try:
            if mode == "single":
                emo = self._collect().get("emotion_images") or {}
                for p in emo.values():
                    if p and os.path.exists(p):
                        return QPixmap(p)
                from pets.pet_registry import (get_fgimages_dir, get_fgimages_prefix,
                                               get_portrait_default_layers)
                d = get_fgimages_dir(self.pet_id) if self.pet_id else ""
                if d:
                    lids = get_portrait_default_layers(self.pet_id) or [0]
                    p = os.path.join(d, f"{get_fgimages_prefix(self.pet_id)}{set_name}_{lids[0]}.png")
                    if os.path.exists(p):
                        return QPixmap(p)
                return QPixmap()
        except Exception:
            pass
        try:
            from .portrait_studio import PortraitStudio
            keep = {k: os.environ.get(k) for k in ("AIPET_LAYER_ADJUST", "AIPET_PET_ID")}
            try:
                # 图层微调对话框正在调 → 用它的“待应用”值（否则改了看不出效果）
                adj = getattr(self, "_live_layer_adjust", None)
                if adj is None:
                    adj = self._collect().get("layer_adjust") or {}
                os.environ["AIPET_LAYER_ADJUST"] = json.dumps(adj, ensure_ascii=False)
                if self.pet_id:
                    os.environ["AIPET_PET_ID"] = self.pet_id
                # 全身 + 透明底（桌宠设置里看的是"桌宠身上那套样子"，不是工坊的半身+场景）
                out, err = PortraitStudio._run_cli(
                    ["preview_full", set_name, ""], timeout=90, pet_id=self.pet_id)
                path = out.splitlines()[-1].strip() if out else ""
                if path and os.path.exists(path):
                    return QPixmap(path)
            finally:
                for k, v in keep.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
        except Exception as e:
            print(f"[Wizard] ⚠ 拼合预览失败: {e}")
        try:
            from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
            d = get_fgimages_dir(self.pet_id) if self.pet_id else ""
            if d:
                pref = get_fgimages_prefix(self.pet_id)
                cands = [f for f in os.listdir(d)
                         if f.startswith(pref) and f.endswith(".png") and "_" in f]
                if cands:
                    return QPixmap(os.path.join(d, sorted(cands)[0]))
        except Exception:
            pass
        return QPixmap()

    def _pix_cache_key(self):
        """预览图缓存键：只有「表情 / 装扮 / 图层微调 / 立绘套」变了才需要重新合成。
        拖动大小、偏移、对话框等几何参数不该触发重合成（那是卡顿的主因）。"""
        try:
            return (self._cur_mode(),
                    str(self._disp().get("2d", {}).get("preview_set") or "a"),
                    json.dumps(getattr(self, "_live_layer_adjust", None)
                               or self._collect().get("layer_adjust") or {}, sort_keys=True),
                    json.dumps(self._emo_edit_values(), sort_keys=True),
                    str(self.cmb_wiz_cloth.currentData() if self.cmb_wiz_cloth.count() else ""))
        except Exception:
            return None

    def _cached_preview(self):
        key = self._pix_cache_key()
        if key is not None and key == getattr(self, "_pix_cache_key_last", None):
            pix = getattr(self, "_pix_cache", None)
            if pix is not None and not pix.isNull():
                return pix
        pix = self._preview_image()
        if pix is not None and not pix.isNull():
            self._pix_cache = pix
            self._pix_cache_key_last = key
        return pix

    def _refresh_display_preview(self):
        try:
            mode = self._cur_mode()
            # 表情管理区：只有「单图 2D 角色」才显示
            try:
                is_single = False
                if self.pet_id:
                    from pets.pet_registry import get_portrait_mode, get_fgimages_dir
                    is_single = bool(get_fgimages_dir(self.pet_id)) and get_portrait_mode(self.pet_id) == "single"
                else:
                    is_single = (self._kind() == "2d"
                                 and self.rb_single.isChecked()
                                 and bool(getattr(self, "_emo_rows", [])))
                self.gb_emo.setVisible(False)        # 表情增删已挪到「立绘素材」页
                try:
                    self.gb_emo_portrait.setVisible(True)
                except Exception:
                    pass
                if is_single and not getattr(self, "_emo_edit_rows", []):
                    self._emo_edit_load()
            except Exception as _e:
                print(f"[Wizard] ⚠ 表情区刷新失败: {_e}")
            v = self._display_values()
            self.disp_preview.set_mode(mode)
            # 几何类调节走缓存（不重新合成 → 丝滑）；只有内容变化才重合成
            self.disp_preview.set_params(v, self._cached_preview() if mode == "2d" else QPixmap())
            cloths = self._cloth_options()
            try:
                self.gb_wiz_cloth.setVisible(bool(cloths) and mode == "2d")
                if cloths and self.cmb_wiz_cloth.count() != len(cloths):
                    self.cmb_wiz_cloth.blockSignals(True)
                    self.cmb_wiz_cloth.clear()
                    for name, cid, hair in cloths:
                        self.cmb_wiz_cloth.addItem(str(name), (name, cid, hair))
                    from .portrait_studio import PortraitStudio as _PS
                    data, _e = _PS._run_cli(["list"], timeout=60, pet_id=self.pet_id)
                    d = json.loads(data.splitlines()[-1]) if data else {}
                    act = str(d.get("active") or "a")
                    cur = str((((d.get("saved") or {}).get(act)) or {}).get("cloth") or "")
                    if cur:
                        for i in range(self.cmb_wiz_cloth.count()):
                            if cur in self.cmb_wiz_cloth.itemText(i):
                                self.cmb_wiz_cloth.setCurrentIndex(i)
                                break
                    self.cmb_wiz_cloth.blockSignals(False)
            except Exception as e:
                print(f"[Wizard] ⚠ 服装栏刷新失败: {e}")
            try:
                self.btn_layer_tune.setVisible(mode == "2d")
                self.lbl_disp_tip.setText(
                    ("2D 立绘：每个表情一张整图，或多张图层拼合。拼合立绘若位置不对"
                     "（穿模 / 错位），用「位置微调」；下面预览就是拼合后的真实样子。")
                    if mode == "2d" else
                    ("Live2D：下面是模型大小与位置（与 2D 立绘完全独立设置）；"
                     "实时预览请点右上「打开立绘工坊」。"))
            except Exception:
                pass
        except Exception as e:
            print(f"[Wizard] ⚠ 刷新显示预览失败: {e}")


    # ── 步骤 6：语音 ──
    # ── 步骤 6：触摸互动（全身可摸：头/胸口/小腹/下体/大腿/小腿/脚/胳膊/手掌）──
    def _page_touch(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)
        lay.addWidget(QLabel("触摸互动（被摸到时像「摸头」一样回应）"))
        tip = QLabel("· 开启后，鼠标点到身上对应区域并拖动（抚摸）或轻点，桌宠都会回应；\n"
                     "· 九个部位的范围可以自由调整大小与位置：点下面按钮打开编辑器，\n"
                     "  在立绘上直接拖框（Live2D 角色会把框画在实时预览窗口上面，边看边调）。")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        self.chk_touch = QCheckBox("启用全身触摸互动（头 / 胸口 / 小腹 / 下体 / 大腿 / 小腿 / 脚 / 胳膊 / 手掌）")
        # 默认**不勾**：触摸区域是逐角色调的，没做过的角色不该凭空开
        # （下面几行会用该角色真实的 touch_enabled 覆盖一次）
        self.chk_touch.setChecked(False)
        lay.addWidget(self.chk_touch)

        gb = QGroupBox("部位区域（可在编辑器里拖动/缩放 / 增删，保存后桌宠立刻生效）")
        gv = QVBoxLayout(gb)
        try:
            from tool.touch_areas import AREAS
            _names = "、".join(n for _k, n, _d, _a, _b in AREAS)
        except Exception:
            _names = "头、胸口、小腹、下体、大腿、小腿、脚、胳膊、手掌"
        row = QLabel(_names)
        row.setWordWrap(True)
        row.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        gv.addWidget(row)
        btn = QPushButton("🎯 打开「触摸区域调节」界面（拖动框调整位置/大小）")
        btn.setMinimumHeight(38)
        btn.clicked.connect(self._open_touch_editor)
        gv.addWidget(btn)
        self.lbl_touch_state = QLabel("")
        self.lbl_touch_state.setStyleSheet(f"color:{ok_text().name()};font-size:12px;")
        self.lbl_touch_state.setWordWrap(True)
        gv.addWidget(self.lbl_touch_state)
        lay.addWidget(gb)
        lay.addStretch()
        try:
            from tool.touch_areas import touch_enabled, get_pet_areas, has_areas
            _pid = getattr(self, "pet_id", None)
            _configured = bool(has_areas(_pid))
            self.chk_touch.setChecked(bool(touch_enabled(_pid)))
            from tool.touch_areas import custom_keys as _ck
            _n = len(get_pet_areas(_pid))
            _c = len(_ck(_pid))
            if _configured:
                self.lbl_touch_state.setText(
                    f"当前已有 {_n} 个部位区域" + (f"（其中自定义 {_c} 个，可在编辑器里删）" if _c else ""))
            else:
                self.lbl_touch_state.setText(
                    "这个角色还没配过触摸区域 → 默认不启用（照旧：摸头 / 点下半身开输入框）。\n"
                    f"想让身体部位能摸，点上面「调节触摸区域」把 {_n} 个框拖到她的身上并保存，即为该角色开启。")
        except Exception:
            pass
        return w

    def _open_touch_editor(self):
        """打开触摸区域编辑器（新建流程里没有 pet_id → 提示先完成保存）"""
        try:
            from pcl_launcher.touch_editor import TouchAreaEditor
            pid = getattr(self, "pet_id", None)
            if not pid:
                page_msg(self, "触摸区域调节", "新建中的角色还没有保存，触摸区域要在角色创建完成后再调。\n"
                    "先走完向导点「完成」，再回到这一步打开编辑器即可。")
                return
            ed = getattr(self, "_touch_editor", None)
            try:
                if ed is not None:
                    ed.isHidden()
            except Exception:
                ed = None
            if ed is None:
                ed = TouchAreaEditor(pid, None)
                self._touch_editor = ed
            ed.show(); ed.raise_(); ed.activateWindow()
            try:
                ed.saved.connect(lambda _p: self.lbl_touch_state.setText("✅ 触摸区域已保存"))
            except Exception:
                pass
        except Exception as e:
            print(f"[Wizard] ⚠ 打开触摸编辑器失败: {e}")
            page_msg(self, "触摸区域调节", f"打开失败：{e}")

    def _page_voice(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        g1 = QGroupBox("短语音（日语 · GPT-SoVITS 逐句短句 · 音色=参考音频，语气=情绪）")
        l1 = QVBoxLayout(g1)
        self.chk_short = QCheckBox("启用短语音（桌宠说话发声）")
        l1.addWidget(self.chk_short)
        r1 = QHBoxLayout()
        self.ed_short_dir = QLineEdit()
        self.ed_short_dir.setPlaceholderText("语音包文件夹（内含各情绪子目录，每个子目录放 ref.wav/mp3 + asr.txt）")
        b1 = QPushButton("选择文件夹…")
        b1.clicked.connect(lambda: self._pick_dir(self.ed_short_dir))
        r1.addWidget(self.ed_short_dir, 1)
        r1.addWidget(b1)
        l1.addLayout(r1)
        r2 = QHBoxLayout()
        self.ed_short_ref = QLineEdit()
        self.ed_short_ref.setPlaceholderText("或：只选一个参考音频（同一音色，情绪只影响合成语气）")
        b2 = QPushButton("选择音频…")
        b2.clicked.connect(lambda: self._pick_file(self.ed_short_ref, "音频 (*.wav *.mp3 *.flac)"))
        r2.addWidget(self.ed_short_ref, 1)
        r2.addWidget(b2)
        l1.addLayout(r2)
        self.ed_short_text = QLineEdit()
        self.ed_short_text.setPlaceholderText("参考音频对应文本（日语，如 はよう、いくぞ、ごしゅじん！；可留空）")
        l1.addWidget(self.ed_short_text)
        l1.addWidget(QLabel("不填则使用角色自带/默认（无参考音频时不会发声，不影响文字聊天）"))
        lay.addWidget(g1)

        g2 = QGroupBox("长语音（中文 · F5-TTS 长文本朗读 · 音色=参考音频）")
        l2 = QVBoxLayout(g2)
        self.chk_long = QCheckBox("启用长语音（长文本模式 / 大段朗读）")
        l2.addWidget(self.chk_long)
        r3 = QHBoxLayout()
        self.ed_long_ref = QLineEdit()
        d_ref, d_txt = default_long_ref()
        self.ed_long_ref.setPlaceholderText(f"参考音频 wav（留空使用默认：{os.path.basename(d_ref) if d_ref else '无'}）")
        b3 = QPushButton("选择音频…")
        b3.clicked.connect(lambda: self._pick_file(self.ed_long_ref, "音频 (*.wav *.mp3 *.flac)"))
        r3.addWidget(self.ed_long_ref, 1)
        r3.addWidget(b3)
        l2.addLayout(r3)
        self.ed_long_text = QLineEdit()
        self.ed_long_text.setPlaceholderText("参考音频文本（中文，如 能和老师在一起，我真的，好高兴！）")
        l2.addWidget(self.ed_long_text)
        lay.addWidget(g2)

        tip = QLabel("说明：短语音合成的是【日语】（推理时用日语参考音频，情绪按台词语气切换）；\n"
                     "长语音合成的是【中文】（长文本模式整段朗读）。两者都可以不配，随时在设置里改。")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        lay.addWidget(tip)
        lay.addStretch()
        return w

    def _pick_dir(self, target_edit):
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d:
            target_edit.setText(d)

    def _pick_file(self, target_edit, filt):
        p, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filt)
        if p:
            target_edit.setText(p)

    # ── 步骤 6：人设 ──
    def _page_persona(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("从其他角色复制人设："))
        self.cb_copy_from = QComboBox()
        self.cb_copy_from.addItem("（不复制）", "")
        try:
            from pets.pet_registry import get_pet_ids
            for pid in get_pet_ids():
                self.cb_copy_from.addItem(pid, pid)
        except Exception:
            pass
        b = QPushButton("复制过来")
        b.clicked.connect(self._copy_persona)
        top.addWidget(self.cb_copy_from)
        top.addWidget(b)
        top.addStretch()
        lay.addLayout(top)

        lay.addWidget(QLabel("短文本人设（桌宠日常对话用）—— 与「提示词 → 短文本」是同一份文件："))
        self.ed_p_short = QPlainTextEdit()
        self.ed_p_short.setPlaceholderText("例如：你叫小满，是一个活泼爱笑的桌宠少女……")
        lay.addWidget(self.ed_p_short, 1)
        lay.addWidget(QLabel("长文本人设（QQ 聊天 / 长文本模式用）—— 与「提示词 → 长文本」同一份文件："))
        self.ed_p_long = QPlainTextEdit()
        self.ed_p_long.setPlaceholderText("可以写得更详细：背景设定、说话风格、主人在意的事……")
        lay.addWidget(self.ed_p_long, 1)
        lay.addWidget(QLabel("提示：这里保存后，「提示词」页面里看到的就是同一份内容（双向同步）。"))
        return w

    def _copy_persona(self):
        pid = self.cb_copy_from.currentData()
        if not pid:
            return
        base = os.path.join(pets_dir(), pid)
        try:
            ps = open(os.path.join(base, "prompt.txt"), encoding="utf-8").read()
            self.ed_p_short.setPlainText(ps)
        except Exception:
            pass
        try:
            pl = open(os.path.join(base, "longtext_prompt.txt"), encoding="utf-8").read()
            self.ed_p_long.setPlainText(pl)
        except Exception:
            self.ed_p_long.setPlainText(self.ed_p_short.toPlainText())
        self.hint.setText(f"已从 {pid} 复制人设，可继续修改")

    # ── 步骤 7：完成 ──
    def _page_done(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setTextFormat(Qt.RichText)
        lay.addWidget(self.lbl_summary)
        tip = QLabel("创建后：桌宠卡片会出现这个角色 → 点「⭐ 设为活动」→ 启动桌宠即可。\n"
                     "之后想改任何一项，点卡片上的「⚙ 设置」重新进入本向导。")
        tip.setStyleSheet(f"color:{Gray2.name()};font-size:12px;")
        lay.addWidget(tip)
        lay.addStretch()
        return w

    def _refresh_summary(self):
        s = self._collect()
        emo_n = len([k for k, v in (s["emotion_images"] or {}).items() if v])
        rows = [
            ("桌宠 ID", s["id"] or "（未填）"),
            ("名称", s["name"] or "（未填）"),
            ("形象", "Live2D 模型" if s["kind"] == "live2d" else
                     ("2D 立绘 · 每个表情一张图" if s.get("portrait_mode") == "single"
                      else "2D 立绘 · 多图层拼合")),
        ]
        if s["kind"] == "2d":
            rows.append(("立绘素材", f"{emo_n} 个表情图，前缀 {s.get('fgimages_prefix') or '（未填）'}"
                                   if s.get("portrait_mode") == "single" else
                                   f"图层目录 {os.path.basename(s.get('layer_src_dir') or '') or '（未选）'}，"
                                   f"前缀 {s.get('fgimages_prefix') or '（未填）'}"))
        else:
            rows.append(("Live2D 模型", os.path.basename(s.get("live2d_src") or "（未选）")))
        rows.append(("短语音(日语)", f"启用，{len(s.get('short_voice_emotions') or []) or ('单一音色' if s.get('short_voice_single') else 0)} 个情绪"
                                 if (s.get("short_voice_dir") or s.get("short_voice_single")) else "未配置"))
        rows.append(("长语音(中文)", "使用自定义参考音频" if s.get("long_ref_src") else "使用默认参考音频"))
        rows.append(("人设字数", f"短 {len(s.get('prompt_short') or '')} 字 / 长 {len(s.get('prompt_long') or '')} 字"))
        html = "<b>即将创建/保存：</b><br>" + "<br>".join(f"· {k}：{v}" for k, v in rows)
        self.lbl_summary.setText(html)

    # ── 收集 & 落盘 ──
    def _collect(self) -> dict:
        s = dict(self._spec)
        s.update({
            "id": (self.pet_id
                   or self.ed_id.text().strip()
                   or slugify_id(self.ed_name.text())
                   or self._suggest_id()),
            "name": self.ed_name.text().strip(),
            "display_name": self.ed_disp.text().strip() or self.ed_name.text().strip(),
            "intro": self.ed_intro.text().strip(),
            "avatar_src": self.ed_avatar.text().strip(),
            "kind": self._kind(),
            "portrait_mode": "single" if self.rb_single.isChecked() else "layers",
            "fgimages_prefix": self.ed_prefix.text().strip(),
            "layer_src_dir": self.ed_layer_dir.text().strip(),
            "live2d_src": self.ed_l2d.text().strip(),
            "short_voice_dir": self.ed_short_dir.text().strip() if self.chk_short.isChecked() else "",
            "short_voice_single": self.ed_short_ref.text().strip() if self.chk_short.isChecked() else "",
            "short_voice_text": self.ed_short_text.text().strip(),
            "long_ref_src": self.ed_long_ref.text().strip() if self.chk_long.isChecked() else "",
            "long_ref_text": self.ed_long_text.text().strip(),
            "prompt_short": self.ed_p_short.toPlainText(),
            "prompt_long": self.ed_p_long.toPlainText(),
        })
        # 显示与对话框（2D / Live2D 两套完全独立的设置）
        try:
            self._write_back_disp()
            d2 = dict(self._disp().get("2d") or {})
            dl = dict(self._disp().get("live2d") or {})
            s["display_mode"] = self._cur_mode()
            s["display_2d"] = d2
            s["display_live2d"] = dl
            s["sets"] = d2.get("sets") or ["a"]
            # 兼容旧键（老版本 pet.json 用的字段）
            s["text_box"] = dl.get("text_box") if s["display_mode"] == "live2d" else d2.get("text_box")
            s["text_font_scale"] = (dl.get("font_scale") if s["display_mode"] == "live2d"
                                    else d2.get("font_scale"))
            s["display_height_ratio"] = (dl.get("height_ratio") if s["display_mode"] == "live2d"
                                         else d2.get("height_ratio"))
        except Exception as e:
            print(f"[Wizard] ⚠ 读取显示设置失败: {e}")
        # 图层微调（对话框里刚改过就先用待应用的；否则沿用角色已有配置）
        try:
            pend = getattr(self, "_pending_layer_adjust", None)
            if pend is not None:
                s["layer_adjust_pending"] = pend
        except Exception:
            pass
        try:
            if self.gb_wiz_cloth.isVisible() and self.cmb_wiz_cloth.count():
                d = self.cmb_wiz_cloth.currentData()
                if d:
                    s["default_cloth"] = d[0]
        except Exception:
            pass
        if s["kind"] == "2d" and s["portrait_mode"] == "single":
            mapping = {}
            # 显示步骤里增删过的表情优先（用户可能在这里加/删）
            try:
                _em = self._emo_edit_values()
                if _em:
                    mapping.update(_em)
            except Exception:
                pass
            for _row, ed, le in self._emo_rows:
                emo = ed.text().strip()
                p = le.text().strip()
                if emo and p and os.path.exists(p):
                    mapping[emo] = p
            s["emotion_images"] = mapping
        elif s["kind"] == "2d":
            # 图层映射 → portrait 块
            pt = {"mode": "layers", "prefix": s["fgimages_prefix"], "sets": ["a"],
                  "emotions": {}, "clothes": {}, "decors": {},
                  "default_emotion": "平静"}
            d = self.cb_emo_default.currentData() or 0
            for e, cb in self._emo_combos.items():
                v = cb.currentData() or 0
                if v:
                    pt["emotions"][e] = int(v)
            if d:
                pt["emotions"]["平静"] = int(d)
            for i in range(self.cloth_rows.count()):
                holder = self.cloth_rows.itemAt(i).widget()
                if holder is None:
                    continue
                combos = holder.findChildren(QComboBox)
                ed = holder.findChildren(QLineEdit)
                if not ed or len(combos) < 2:
                    continue
                cname = ed[0].text().strip()
                if cname:
                    pt["clothes"][cname] = {"cloth": int(combos[0].currentData() or 0),
                                            "hair": int(combos[1].currentData() or 0)}
            for i in range(self.decor_rows.count()):
                holder = self.decor_rows.itemAt(i).widget()
                if holder is None:
                    continue
                combos = holder.findChildren(QComboBox)
                ed = holder.findChildren(QLineEdit)
                if not ed or not combos:
                    continue
                dname = ed[0].text().strip()
                v = combos[0].currentData() or 0
                if dname and v:
                    pt["decors"][dname] = int(v)
            if not pt["emotions"].get("平静"):
                pt["emotions"]["平静"] = d or 0
            s["portrait"] = pt
        # 单一音色 → 情绪列表
        if s.get("short_voice_single"):
            s["short_voice_emotions"] = list(EMOTION_PRESET)
        return s

    def _finish(self):
        s = self._collect()
        pid = s["id"]
        if not pid:
            self.hint.setText("请先填写桌宠 ID")
            self._goto(0)
            return
        import re
        if not self.is_edit and not re.fullmatch(r"[A-Za-z0-9_\-]{2,32}", pid):
            self.hint.setText("ID 只能用 2-32 位英文/数字/下划线/连字符（它会作为角色包文件夹名）")
            self._goto(0)
            return
        from pets.pet_registry import get_pet_ids
        if not self.is_edit and pid in get_pet_ids():
            self.hint.setText(f"ID「{pid}」已存在，请换一个")
            self._goto(0)
            return
        if not s["name"]:
            self.hint.setText("请填写桌宠名称")
            self._goto(0)
            return
        if s["kind"] == "2d" and s["portrait_mode"] == "single" and not s["emotion_images"]:
            if not page_confirm(self, "还没有立绘",
                                "你还没有为任何表情选择图片。",
                                "没有立绘时桌宠也可以聊天，但不会显示形象。仍要继续吗？",
                                ok_text="继续创建", danger=False):
                return
        try:
            _pid, notes = create_or_update_pet(s)
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "创建失败", f"{e}\n\n{traceback.format_exc()[:600]}")
            return
        self._spec = s
        msg = "\n".join(notes) or "已保存"
        page_msg(self, "完成", f"「{s['name']}」已{'保存' if self.is_edit else '创建'}！\n\n{msg}\n\n"
                                              "下一步：在桌宠卡片点「⭐ 设为活动」，再启动桌宠。")
        self.saved.emit(_pid)
        self.accept()

    # ── 编辑模式：回填现有配置 ──
    def _load_existing(self):
        try:
            from pets.pet_registry import get_pet_config
            cfg = get_pet_config(self.pet_id) or {}
        except Exception:
            cfg = {}
        self.ed_id.setText(self.pet_id)
        self.ed_id.setEnabled(False)
        self.ed_name.setText(str(cfg.get("name") or ""))
        self.ed_disp.setText(str(cfg.get("display_name") or ""))
        self.ed_intro.setText(str(cfg.get("intro") or ""))
        av = str(cfg.get("avatar") or "")
        if av:
            p = os.path.join(pets_dir(), self.pet_id, av)
            self.ed_avatar.setText(p if os.path.exists(p) else av)
        m = cfg.get("model") or {}
        # ⚠ 以前只要角色「有 Live2D 模型」就勾 Live2D → 打开桌宠设置总是进 Live2D 界面，
        #   2D 立绘的步骤被跳过。现在按 pet.json 的 model.default 决定（有 2D 素材就默认 2D）。
        try:
            from pets.pet_registry import get_fgimages_dir
            has_fg = bool(get_fgimages_dir(self.pet_id))
            _def = str(m.get("default") or ("2d" if has_fg else "live2d")).lower()
            if _def == "live2d":
                self.rb_l2d.setChecked(True)
            else:
                self.rb_2d.setChecked(True)
            print(f"[Wizard] 编辑 {self.pet_id}: default={_def} 有2D素材={has_fg}")
        except Exception as e:
            print(f"[Wizard] ⚠ 判断显示方式失败: {e}")
        self.ed_prefix.setText(str(m.get("fgimages_prefix") or self.pet_id))
        try:
            l2d_dir = os.path.join(pets_dir(), self.pet_id, str(m.get("live2d_dir") or "live2d"))
            for f in os.listdir(l2d_dir) if os.path.isdir(l2d_dir) else []:
                if f.endswith(".model3.json"):
                    self.ed_l2d.setText(os.path.join(l2d_dir, f))
                    break
        except Exception:
            pass
        v = cfg.get("voices") or {}
        if v.get("short_emotions"):
            self.chk_short.setChecked(True)
            sd = os.path.join(pets_dir(), self.pet_id, str(v.get("short_ref_dir") or "voices/short"))
            if os.path.isdir(sd):
                self.ed_short_dir.setText(sd)
        if v.get("long_ref_audio"):
            self.chk_long.setChecked(True)
            lr = os.path.join(pets_dir(), self.pet_id, str(v.get("long_ref_audio")))
            self.ed_long_ref.setText(lr if os.path.exists(lr) else "")
            self.ed_long_text.setText(str(v.get("long_ref_text") or ""))
        # 人设
        try:
            for kind, box in (("short", self.ed_p_short), ("long", self.ed_p_long)):
                rel = (cfg.get("prompt") or {}).get(kind) or ("prompt.txt" if kind == "short" else "longtext_prompt.txt")
                p = os.path.join(pets_dir(), self.pet_id, rel)
                if os.path.exists(p):
                    box.setPlainText(open(p, encoding="utf-8").read())
        except Exception:            pass
        # 立绘：已有素材 → 默认按图层模式展示
        fg = os.path.join(pets_dir(), self.pet_id, "fgimages")
        idxs = find_index_files(fg)
        pt = cfg.get("portrait") or {}
        if pt.get("mode") == "layers" or (idxs and not pt):
            self.rb_layers.setChecked(True)
            if idxs:
                self.ed_layer_dir.setText(fg)
                self._load_layers()
                self._apply_portrait_block(pt)
        self.btn_finish.setText("保存修改")
        # 显示与对话框：回填两套设置（2D / Live2D 各自独立）
        try:
            inter = cfg.get("interaction") or {}
            d2 = dict(m.get("display_2d") or m.get("display") or {})
            dl = dict(m.get("display_live2d") or {})
            if d2.get("height_ratio") is None:
                _hr = (m.get("display") or {}).get("portrait_height_ratio")
                if _hr is not None:
                    d2["height_ratio"] = _hr
            if dl.get("height_ratio") is None:
                dl["height_ratio"] = m.get("live2d_window_height_ratio", 0.85)
            if dl.get("width_ratio") is None:
                dl["width_ratio"] = m.get("live2d_window_ratio", 0.67)
            # 文本区域：新模式键优先，其次旧键
            _fallback_tb = inter.get("text_box")
            d2["text_box"] = inter.get("text_box_2d") or _fallback_tb
            dl["text_box"] = inter.get("text_box_live2d") or _fallback_tb
            d2["font_scale"] = float(inter.get("text_font_scale_2d",
                                               inter.get("text_font_scale", 1.0)) or 1.0)
            dl["font_scale"] = float(inter.get("text_font_scale_live2d",
                                               inter.get("text_font_scale", 1.0)) or 1.0)
            self._disp_data = self._disp_defaults()
            for k, v in d2.items():
                if v is not None:
                    self._disp_data["2d"][k] = v
            for k, v in dl.items():
                if v is not None:
                    self._disp_data["live2d"][k] = v
            self._disp_data["2d"]["sets"] = [str(x) for x in
                                            (m.get("sets_available") or m.get("fgimages_sets") or ["a"])]
            # 显示方式：按 pet.json 的 default 勾选
            _mode = str(m.get("default") or "2d").lower()
            (self.rb_disp_lv if _mode == "live2d" else self.rb_disp_2d).setChecked(True)
            self._cur_disp_mode = _mode
            self.disp_stack.setCurrentIndex(0 if _mode != "live2d" else 1)
            # Live2D 信息
            try:
                from pets.pet_registry import get_live2d_model_json
                mj = get_live2d_model_json(self.pet_id) or ""
                self.lbl_lv_info.setText(("模型：" + os.path.basename(mj)) if mj
                                         else "（该角色没有 Live2D 模型）")
                self.rb_disp_lv.setEnabled(bool(mj))
            except Exception:
                pass
            try:
                from pets.pet_registry import get_fgimages_dir
                self.rb_disp_2d.setEnabled(bool(get_fgimages_dir(self.pet_id)))
            except Exception:
                pass
            self._ensure_two_sets_state()
            self._bind_disp_widgets()
            self._refresh_display_preview()
        except Exception as e:
            print(f"[Wizard] ⚠ 回填显示设置失败: {e}")


    def _apply_portrait_block(self, pt: dict):
        """编辑模式：把 pet.json 里的 portrait 映射回填到界面"""
        try:
            pt = pt or {}
            d = int(pt.get("emotions", {}).get("平静") or 0)
            if d:
                for i in range(self.cb_emo_default.count()):
                    if self.cb_emo_default.itemData(i) == d:
                        self.cb_emo_default.setCurrentIndex(i)
                        break
            for emo, cb in self._emo_combos.items():
                v = int(pt.get("emotions", {}).get(emo) or 0)
                if not v:
                    continue
                for i in range(cb.count()):
                    if cb.itemData(i) == v:
                        cb.setCurrentIndex(i)
                        break
            # 服装/装饰：清掉默认行再按配置重建
            while self.cloth_rows.count():
                w = self.cloth_rows.takeAt(0).widget()
                if w:
                    w.deleteLater()
            for name, c in (pt.get("clothes") or {}).items():
                self._add_cloth_row(name, c.get("cloth"), c.get("hair"))
            while self.decor_rows.count():
                w = self.decor_rows.takeAt(0).widget()
                if w:
                    w.deleteLater()
            for name, lid in (pt.get("decors") or {}).items():
                self._add_decor_row(name, lid)
            # 选中值
            for i in range(self.cloth_rows.count()):
                holder = self.cloth_rows.itemAt(i).widget()
                if holder is None:
                    continue
                ed = holder.findChildren(QLineEdit)
                cbs = holder.findChildren(QComboBox)
                if not ed or len(cbs) < 2:
                    continue
                c = (pt.get("clothes") or {}).get(ed[0].text().strip())
                if not c:
                    continue
                for cb, val in ((cbs[0], c.get("cloth")), (cbs[1], c.get("hair"))):
                    for i2 in range(cb.count()):
                        if cb.itemData(i2) == int(val or 0):
                            cb.setCurrentIndex(i2)
                            break
            for i in range(self.decor_rows.count()):
                holder = self.decor_rows.itemAt(i).widget()
                if holder is None:
                    continue
                ed = holder.findChildren(QLineEdit)
                cbs = holder.findChildren(QComboBox)
                if not ed or not cbs:
                    continue
                v = (pt.get("decors") or {}).get(ed[0].text().strip())
                if v is None:
                    continue
                for i2 in range(cbs[0].count()):
                    if cbs[0].itemData(i2) == int(v):
                        cbs[0].setCurrentIndex(i2)
                        break
        except Exception as e:
            print(f"[PetWizard] 回填立绘映射失败: {e}")
