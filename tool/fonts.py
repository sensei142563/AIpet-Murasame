# -*- coding: utf-8 -*-
"""界面字体：项目自带 fonts/ 里的五款中日文字体，**启动器与桌宠共用同一套**。

- `fonts/manifest.json` 记录 [{id, label, file, desc, license}]（五款都是 SIL OFL 1.1）
- 用户的选择存在 config.json 的 `ui_font`（字体 id）；空/缺失 = 用自带的
  `思源黑体Bold.otf`（也就是以前的行为，不受影响）
- 注册用 `QFontDatabase.addApplicationFont()` → 返回 Qt 里的**真实族名**
  （字体内部族名不一定等于文件名，必须回读）

为什么放 tool/：启动器（冻结 exe）和桌宠（源码）都要用；写一份省得两边各写一遍。
"""
import json
import os

_CACHE = {}


def fonts_dir() -> str:
    """项目根目录下的 fonts/"""
    base = ""
    try:
        from tool.paths import app_base_dir
        base = app_base_dir()
    except Exception:
        base = ""
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "fonts")


def list_fonts() -> list:
    """可用的字体列表（文件缺失的自动跳过）"""
    out = []
    try:
        p = os.path.join(fonts_dir(), "manifest.json")
        with open(p, encoding="utf-8") as f:
            data = json.load(f) or {}
        for it in (data.get("fonts") or []):
            fp = os.path.join(fonts_dir(), str(it.get("file") or ""))
            try:
                ok = os.path.isfile(fp) and os.path.getsize(fp) > 100 * 1024
            except Exception:
                ok = False
            if ok:
                d = dict(it)
                d["path"] = fp
                out.append(d)
    except Exception as e:
        print(f"[Fonts] ⚠ 读取字体清单失败: {e}")
    return out


def ensure_loaded(font_id: str) -> str:
    """注册某款字体 → Qt 真实族名（失败返回 ""）"""
    fid = str(font_id or "").strip()
    if not fid:
        return ""
    if fid in _CACHE:
        return _CACHE[fid]
    fam = ""
    try:
        from PyQt5.QtGui import QFontDatabase
        for it in list_fonts():
            if str(it.get("id")) == fid:
                _id = QFontDatabase.addApplicationFont(it["path"])
                if _id is not None and _id >= 0:
                    fams = QFontDatabase.applicationFontFamilies(_id) or []
                    fam = str(fams[0]) if fams else ""
                if not fam:
                    print(f"[Fonts] ⚠ 字体文件已加载但取不到族名: {it.get('file')}")
                break
        else:
            print(f"[Fonts] ⚠ 清单里没有字体 id: {fid}")
    except Exception as e:
        print(f"[Fonts] ⚠ 加载字体失败 {fid}: {e}")
    _CACHE[fid] = fam
    return fam


def current_font_id() -> str:
    """config.json 里选的字体 id（空 = 用自带的思源黑体）"""
    try:
        from tool.config import get_config
        return str(get_config("./config.json").get("ui_font") or "").strip()
    except Exception:
        return ""


def current_family() -> str:
    """当前应该用的 Qt 族名（没选或加载失败返回 ""，调用方自己回退）"""
    return ensure_loaded(current_font_id())
