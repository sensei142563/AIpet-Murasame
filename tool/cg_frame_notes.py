# -*- coding: utf-8 -*-
"""给每张 CG 的**每一帧**（大图）写说明 —— 差分/体液/表情都在这几帧里

为什么需要：一个 CG 组里的大图不是同一张，而是"同一场面的不同合成版本"
（干净 → 体外 → 体内 → 颜面 这种）。只描述最后一帧的话，
AI 挑到第 3 帧时画面和描述对不上，就会"用错 CG"。

· 普通 CG：用视觉模型逐帧描述
· 成人向：**不送云端**，用本地像素分析给出"液体出现在什么位置"（脸/身体上方/画面下方），
  够 AI 判断 颜射/体内/体外；不满意可以直接改 剧情素材/CG/_CG差分说明.csv
用法：python tool/cg_frame_notes.py [--adult-cloud]
"""
import csv
import io
import os
import re
import sys
import threading
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import assets as A  # noqa: E402
from story import caption as C  # noqa: E402

SHEET = "_CG差分说明.csv"
BIG = 1000                      # 宽 ≥1000 才算"合成成品帧"
_lock = threading.Lock()


def sheet_path() -> str:
    d = A.cg_root() or os.path.join(A.BASE, "剧情素材", "CG")
    return os.path.join(d, SHEET)


def load_notes() -> dict:
    """{组: {帧: 说明}}"""
    out = {}
    p = sheet_path()
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8-sig", errors="replace", newline="") as fh:
                for row in csv.reader(fh):
                    if len(row) > 2 and row[0].strip() and not row[0].startswith("#"):
                        try:
                            out.setdefault(row[0].strip(), {})[int(row[1])] = row[2].strip()
                        except Exception:
                            pass
        except Exception as e:
            print("⚠ 读差分说明失败：%s" % e)
    return out


def save_notes(notes: dict) -> None:
    p = sheet_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with _lock:
        with open(p, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write("# 每张 CG 的每一帧（合成版本）分别是什么；可直接手改\n")
            w = csv.writer(fh)
            w.writerow(["CG组", "帧", "说明"])
            for g in sorted(notes):
                for fr in sorted(notes[g]):
                    w.writerow([g, fr, notes[g][fr]])


def patch_note(path: str, base_path: str, allow_liquid: bool = True) -> str:
    """给"差分小图"（要叠上去的那张）判断它加在哪儿。

    成人 CG 的 体外/体内/颜面 就是几张不同的小图叠在基准画面上 ——
    这里对比基准图，看新增的白色/亮色像素集中在画的哪一块，够 AI 判断该叠哪张。
    """
    try:
        # ⚠ 差分图是**带透明**的图层，直接 convert('RGB') 会把透明处变黑，
        #   必须先按 alpha 叠到基准图上，再看"叠之前 vs 叠之后"的差别
        a_img = Image.open(base_path).convert("RGBA")
        b_img = Image.open(path).convert("RGBA")
        if b_img.size != a_img.size:
            b_img = b_img.resize(a_img.size)
        comp = Image.alpha_composite(a_img, b_img).convert("RGB")
        a = a_img.convert("RGB")
        b = comp
        x = np.asarray(a, dtype=np.int16)
        y = np.asarray(b, dtype=np.int16)
        white = (y.mean(axis=2) > 195) & (x.mean(axis=2) < 175)
        n_white = int(white.sum())
        # ⚠ 只有成人向才判"白色液体"：普通 CG 的差分是表情/服饰，
        #   用同一套判据会把皮肤、白衣服当成体液（之前就误标过）
        if not allow_liquid:
            n_white = 0
        if n_white < 200:
            # 不一定是体液：可能是表情/装饰，用"和基准图的差异区域"描述
            diff = np.abs(x - y).sum(axis=2) > 40
            if diff.sum() < 200:
                return "和基准几乎一样"
            ys = np.where(diff)[0]
            rel = float(ys.mean()) / max(1, diff.shape[0])
            where = "画面上部" if rel < 0.42 else ("画面中部" if rel < 0.7 else "画面下部")
            return "叠加变化：%s" % where
        ys, xs = np.where(white)
        h, w = white.shape
        rel_y = float(ys.mean()) / max(1, h)
        where = "脸上/上半身" if rel_y < 0.42 else ("身上/胸腹" if rel_y < 0.7 else "下半身/画面下方")
        share = 100.0 * n_white / max(1, h * w)
        if share > 14:            # 大片"亮"多半是皮肤/衣服，不是体液
            return "叠加变化：%s" % where
        return "白色液体：%s（占画面 %.1f%%）" % (where, share)
    except Exception as e:
        return "（本地分析失败：%s）" % str(e)[:40]


def frame_paths(group: str):
    frs = [f for f in (A.any_cg_list().get(group) or [])]
    out = []
    for fr in frs:
        p = A.any_cg_path(group, fr) or A.cg_path(group, fr)
        if not p or not os.path.isfile(p):
            continue
        try:
            w, h = Image.open(p).size
        except Exception:
            continue
        if w >= BIG:
            out.append((fr, p))
    return out


def main() -> int:
    adult_cloud = "--adult-cloud" in sys.argv
    groups = sorted(A.any_cg_list().keys())
    notes = load_notes()
    redo = "--redo-patches" in sys.argv
    todo = []
    for g in groups:
        have = notes.get(g) or {}
        if redo and "成人" not in g:
            have = {k: v for k, v in have.items()
                    if not (v.startswith("叠加变化") or v.startswith("和基准几乎一样"))}
        big = frame_paths(g)                      # 大图：同一 CG 的多个合成版本
        base_p = big[0][1] if big else ""
        for fr, p in big:
            if fr in have and have[fr]:
                continue
            todo.append((g, fr, p, "frame"))
        for pid in (A.cg_patches(g) or []):        # 小图：要叠上去的差分（表情/体液）
            pp = A.cg_patch_path(g, pid)           # ⚠ 必须是"小图"本身，不能用 cg_path（那只返回成品大图）
            if not pp or not os.path.isfile(pp) or not base_p:
                continue
            if pid in have and have[pid]:
                continue
            todo.append((g, pid, pp, "patch"))
    print("共 %d 组，待标注 %d 项" % (len(groups), len(todo)))
    if not todo:
        print("都标过了 →", sheet_path())
        return 0

    qk = C._qwen_key()
    done = 0

    def run_chunk(chunk):
        n = 0
        for g, fid, p, kind in chunk:
            adult = "成人" in g
            note = ""
            if adult:
                big = frame_paths(g)
                base_p = big[0][1] if big else p
                # 用"叠上去之后的合成图"和基准图比，才能看出液体加在哪
                comp = ""
                try:
                    if kind == "patch" and base_p:
                        comp = A.cg_compose(g, big[0][0] if big else None, fid) or ""
                except Exception:
                    comp = ""
                note = patch_note(comp or p, base_p, allow_liquid=True)
            elif kind == "patch":
                try:                                  # 普通 CG 的表情差分 → 让模型看
                    note = C.ask_vision([p], qk) if qk else ""
                except Exception as e:
                    note = ""
                if not note:
                    big = frame_paths(g)
                    note = patch_note(p, big[0][1] if big else p, allow_liquid=False)
            else:
                try:
                    note = C.ask_vision([p], qk) if qk else ""
                except Exception as e:
                    print("  ⚠ %s#%s 识别失败：%s" % (g, fid, str(e)[:70]))
            if note:
                with _lock:
                    notes.setdefault(g, {})[fid] = note
                n += 1
        return n

    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=5) as ex:
        for i, cnt in enumerate(ex.map(run_chunk, [todo[j::5] for j in range(5)]), 1):
            done += cnt
            save_notes(notes)
            print("  第 %d 批完成，累计 %d 项" % (i, done), flush=True)
    save_notes(notes)
    print("✅ 本次标注 %d 项 → %s" % (done, sheet_path()))
    for g in ("成人2_ev306a", "成人2_ev307a", "事件CG_ev303a"):
        n2 = notes.get(g) or {}
        print("  %s: %s" % (g, " | ".join("%s→%s" % (k, v[:28]) for k, v in sorted(n2.items()))[:200]))
    return 0


def _unused():
    for g, fid, p, kind in []:
        adult = "成人" in g
        note = ""
        if kind == "patch" or adult:
            # 差分/成人：本地像素分析（成人图不送云端）
            big = frame_paths(g)
            base_p = big[0][1] if big else p
            note = patch_note(p, base_p)
        else:
            try:
                note = C.ask_vision([p], qk) if qk else ""
            except Exception as e:
                print("  ⚠ %s#%s 识别失败：%s" % (g, fid, str(e)[:70]))
        if note:
            with _lock:
                notes.setdefault(g, {})[fid] = note
            done += 1
        if done % 20 == 0 and done:
            save_notes(notes)
            print("  …已标 %d 项" % done)
        time.sleep(0.1)
    save_notes(notes)
    print("✅ 本次标注 %d 项 → %s" % (done, sheet_path()))
    for g in ("成人2_ev306a", "成人2_ev307a", "事件CG_ev303a"):
        n = notes.get(g) or {}
        print("  %s: %s" % (g, " | ".join("%s→%s" % (k, v[:30]) for k, v in sorted(n.items()))[:200]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
