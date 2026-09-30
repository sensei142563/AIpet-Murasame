# -*- coding: utf-8 -*-
"""立绘画布几何：让「桌宠窗口」和「设置里的预览」用同一套算法。

为什么需要
----------
2D 立绘是**按图层包围盒**合成的：换一件衣服、换一个表情，合成图的宽度就会变。
如果窗口宽度直接跟着这张图走，那么：

  · 换表情/换装时桌宠窗口忽宽忽窄 → 对话框（按窗口宽高归一化）跟着忽大忽小、位置左右跳；
  · 「设置 → 立绘」的预览按**当前这张图**的宽高比画，而桌面窗口用的是"这一套里最宽的那种"，
    于是预览里立绘与对话框的位置和桌面不一致（用户反馈"预览跟实际不一样"）。

做法：把"这一套立绘在某个目标高度下最宽能有多宽"算出来（遍历该套所有服装的身体层 +
发型层，用图层索引里的 left/top/width/height 求包围盒），桌面窗口与预览都用它当画布宽度。
取不到索引/没有素材时返回 (0, 0)，调用方按原样回退（不改变任何现有行为）。
"""
import csv
import os

# 缓存：{(pet_id, set, target_height): (w, h)} 与 {(fg_dir, prefix, set): {id: 几何}}
_size_cache = {}
_idx_cache = {}


def index_geometry(fg_dir: str, prefix: str, set_name: str) -> dict:
    """读图层索引 → {图层号: (left, top, width, height)}（带缓存，读不到返回 {}）"""
    key = (fg_dir, prefix, set_name)
    if key in _idx_cache:
        return _idx_cache[key]
    out = {}
    try:
        path = os.path.join(fg_dir, "%s%s.txt" % (prefix, set_name))
        if os.path.isfile(path):
            with open(path, encoding="utf-16 le") as f:
                for row in csv.reader(f, delimiter="\t"):
                    if len(row) > 9 and str(row[9]).strip().lstrip("-").isdigit():
                        try:
                            out[int(row[9])] = (int(row[2]), int(row[3]),
                                                int(row[4]), int(row[5]))
                        except (ValueError, IndexError):
                            continue
    except Exception:
        out = {}
    _idx_cache[key] = out
    return out


def canvas_size_for(pet_id: str, set_name: str, target_height: float,
                    extra_ids=None) -> tuple:
    """返回这一套立绘在 target_height 下的 (画布宽, 画布高)（屏幕像素）。

    算法与桌宠一致：遍历该套所有服装的「身体层 + 发型层」，逐个求包围盒并按目标高度
    归一，取**最宽**的那个。取不到索引或没有服装时返回 (0, 0)。
    """
    try:
        th = float(target_height)
    except Exception:
        return (0, 0)
    if th <= 0:
        return (0, 0)
    key = (str(pet_id), str(set_name), int(round(th)),
           tuple(int(x) for x in (extra_ids or []) if str(x).strip().lstrip("-").isdigit()))
    if key in _size_cache:
        return _size_cache[key]

    result = (0, 0)
    try:
        from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
        from tool.portrait_outfit import clothes_of
    except Exception:
        return result
    try:
        s = str(set_name or "a")[-1:]
        s = s if s in ("a", "b") else "a"
        fg_dir = get_fgimages_dir(pet_id)
        if not fg_dir:
            return result
        prefix = get_fgimages_prefix(pet_id)
        idx = index_geometry(fg_dir, prefix, s)
        if not idx:
            return result

        cands = []
        for _n, c, h in (clothes_of(s) or []):
            for v in (c, h):
                try:
                    v = int(v or 0)
                except Exception:
                    continue
                if v:
                    cands.append(v)
        for x in (extra_ids or []):
            try:
                cands.append(int(x))
            except Exception:
                continue
        if not cands:
            return result

        # ⚠ 每个图层必须用**同一个缩放**（按最高的那个图层算），不能各自按自己的高度归一：
        #   丛雨 b 套的发型层 bbox 只有 424x147（一小条刘海），单独按目标高度归一后
        #   宽度会被放大 3.3 倍 → 画布被撑到 1384px，而角色本体层只有 209~258px，
        #   于是 2D 桌宠变成「巨大透明窗中央一个小人」（用户 2026-09-30 报「2D 模型还是坏的」）。
        boxes = []
        for lid in sorted(set(cands)):
            g = idx.get(lid)
            if not g:
                continue
            x0, y0, w, h = g[0], g[1], g[2], g[3]
            if h <= 0:
                continue
            boxes.append((x0, y0, x0 + w, y0 + h))
        if not boxes:
            result = (0, 0)
        else:
            max_h = max(b[3] - b[1] for b in boxes)
            scale = float(th) / float(max_h) if max_h > 0 else 0.0
            best_w = max(int(round((b[2] - b[0]) * scale)) for b in boxes)
            best_h = int(round(th))
        result = (best_w, best_h)
    except Exception:
        result = (0, 0)
    _size_cache[key] = result
    return result


def stable_canvas_width(pet_id: str, set_name: str, target_height: float,
                        extra_ids=None) -> int:
    """只要宽度（算不出来返回 0，调用方原样回退）"""
    return int(canvas_size_for(pet_id, set_name, target_height, extra_ids)[0])


def clear_cache() -> None:
    """测试/换角色时清缓存"""
    _size_cache.clear()
    _idx_cache.clear()


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from pets.pet_registry import get_active_pet_id
    pid = get_active_pet_id()
    print("活动角色:", pid)
    for s in ("a", "b"):
        for h in (600, 900, 1200):
            print("  套 %s  高 %-5d → 画布 %s" % (s, h, canvas_size_for(pid, s, h)))
