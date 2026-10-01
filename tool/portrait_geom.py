# -*- coding: utf-8 -*-
"""立绘画布几何：给"桌宠窗口"和"设置里的预览"共用同一套算法。

背景：2D 立绘是"按图层包围盒"合成的，宽度随外观（衣服/姿势）变化。
桌面窗口用的是**稳定画布**（取这套里最宽的那种），设置预览如果按
"当前这张图的宽高比"画，宽度就会比真实窗口窄 → 预览里立绘和对话框的位置
跟桌面不一致（用户反馈）。所以两边都调这里算，保证一致。
"""
import csv
import os


def canvas_size_for(pet_id: str, set_name: str, target_height: float, extra_ids=None) -> tuple:
    """返回 (画布宽, 画布高) 的"屏幕像素"尺寸（按 target_height 缩放）。

    算法与桌宠一致：遍历这套的基础人物 + 动作图层，用图层索引里的
    left/top/width/height 算包围盒，取最宽的那种按 target_height 归一。
    取不到索引时返回 (0, 0)，调用方自行回退。
    """
    try:
        from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
        from tool.portrait_outfit import clothes_of, actions_of
    except Exception:
        return (0, 0)
    try:
        s = str(set_name or "a")[-1:]
        s = s if s in ("a", "b") else "a"
        fg_dir = get_fgimages_dir(pet_id)
        if not fg_dir:
            return (0, 0)
        prefix = get_fgimages_prefix(pet_id)
        idx_path = os.path.join(fg_dir, "%s%s.txt" % (prefix, s))
        idx = {}
        with open(idx_path, encoding="utf-16 le") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) > 9 and str(row[9]).strip().isdigit():
                    try:
                        idx[int(row[9])] = (int(row[2]), int(row[3]), int(row[4]), int(row[5]))
                    except Exception:
                        continue
        if not idx:
            return (0, 0)
        cands = []
        for _n, c, _h in clothes_of(s):
            cands.append(int(c))
        try:
            for _n, a, _o in (actions_of(s, pet_id) or []):
                if a:
                    cands.append(int(a))
        except Exception:
            pass
        if not cands:
            return result

        # ⚠ 每个图层必须用**同一个缩放**（按最高的那个图层算），不能各自按自己的高度归一：
        #   丛雨 b 套的发型层 bbox 只有 424x147（一小条刘海），单独按目标高度归一后
        #   宽度会被放大 3.3 倍 → 画布被撑到 1384px，而角色本体层只有 209~258px，
        #   于是 2D 桌宠变成「巨大透明窗中央一个小人」（用户 2026-09-30 报「2D 模型还是坏的」）。
        # ★ 本地保留 extra_ids（本地立绘修复传进来的额外图层，例如表情/衣服层）：
        #   它们同样**共用上面这一个缩放**，不会被各自归一。
        _extra = []
        try:
            _extra = [int(x) for x in (extra_ids or []) if str(x).strip().isdigit()]
        except Exception:
            _extra = []
        boxes = []
        for lid in sorted(set(list(cands) + _extra)):
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
        return (0, 0)
