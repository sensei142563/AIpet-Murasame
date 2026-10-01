# -*- coding: utf-8 -*-
"""扫描 GPT-SoVITS 里**训练好的角色语音模型**（供向导「短语音」里选择）。

目录约定同官方：`GPT_weights*/` 放 .ckpt，`SoVITS_weights*/` 放 .pth；
同一角色的两份按文件名前缀配对（natsume-e10.ckpt ↔ natsume_e8_s248.pth），各取最新一份。
"""
import os


def _base() -> str:
    try:
        from tool.paths import app_base_dir
        return os.path.join(app_base_dir(), "GPT-SoVITS")
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "GPT-SoVITS")


def list_trained_models() -> list:
    """→ [(角色 key, 标签, gpt 相对路径, sovits 相对路径)]（按角色名排序）"""
    out = []
    base = _base()
    if not os.path.isdir(base):
        return out

    def _scan(prefix, exts):
        found = {}
        for d in sorted(os.listdir(base)):
            dp = os.path.join(base, d)
            if not (d.startswith(prefix) and os.path.isdir(dp)) or d.endswith("pretrained"):
                continue
            for f in os.listdir(dp):
                if not f.lower().endswith(exts):
                    continue
                fp = os.path.join(dp, f)
                if not os.path.isfile(fp):
                    continue
                key = f.split("-")[0].split("_")[0].split(".")[0].lower()
                if not key:
                    continue
                try:
                    mt = os.path.getmtime(fp)
                except Exception:
                    mt = 0
                if key not in found or mt > found[key][2]:
                    found[key] = ("%s/%s" % (d, f), f, mt)
        return found

    try:
        gpts = _scan("GPT_weights", (".ckpt",))
        sov = _scan("SoVITS_weights", (".pth",))
        for key in sorted(set(gpts) & set(sov)):
            g, gn, _ = gpts[key]
            s, sn, _ = sov[key]
            out.append((key, "%s：%s + %s" % (key, gn, sn), g, s))
    except Exception as e:
        print(f"[GSVModels] ⚠ 扫描训练好的模型失败: {e}")
    return out


def find_for_pet(pet_id: str):
    """按角色 ID 找它自己的模型 → (gpt 相对路径, sovits 相对路径) 或 (None, None)"""
    key = str(pet_id or "").strip().lower()
    if not key:
        return (None, None)
    for k, _label, g, s in list_trained_models():
        if k == key:
            return (g, s)
    return (None, None)
