# -*- coding: utf-8 -*-
"""给「没有归属」的 CG（主要是 Q 版 SD 图）自动定归属。

判据（按可靠度排序）：
 1. 解包剧本里这张图出现时，附近台词有没有直接叫某个角色的名字（茉子/芳乃/丛雨…）；
 2. 视觉识别出来的画面描述里的外貌特征（绿发/银发/金发…）对应到角色；
 3. 同一个角色自己的 CG 描述里用过的特征词（自学习）。
结果写进 剧情素材/CG/_CG归属表.csv（人工标注优先，程序不会覆盖你写过的行）。
"""
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import assets as A  # noqa: E402

# 角色 → 常见外观关键词（用来从"画面描述"里认人）
LOOK = {
    "murasame": ("绿发", "淺绿", "浅绿", "绿瞳", "绿色长发", "蝴蝶结", "丛雨"),
    "mako": ("黑发", "黑色长发", "马尾", "忍者", "围巾", "苦无", "茉子"),
    "fano": ("银发", "白发", "银色", "白色长发", "巫女", "芳乃"),
    "rena": ("金发", "金色", "蕾娜", "レナ"),
    "koharu": ("粉发", "粉色", "小春", "短发"),
    "roka": ("芦花", "棕发", "茶色"),
}
NAMES = {"丛雨": "murasame", "茉子": "mako", "芳乃": "fano", "蕾娜": "rena",
         "小春": "koharu", "芦花": "roka"}


def from_context(group: str) -> str:
    """剧本上下文里有没有直接出现角色名"""
    ctx = A.cg_context(group) or ""
    if not ctx:
        return ""
    hit = {}
    for nm, pid in NAMES.items():
        if nm in ctx:
            hit[pid] = hit.get(pid, 0) + 1
    if not hit:
        return ""
    return max(hit.items(), key=lambda x: x[1])[0]


HAIR = ("绿发", "浅绿", "淺绿", "绿瞳", "黑发", "银发", "白发", "银色", "白色长发",
        "金发", "金色", "粉发", "粉色", "紫发", "棕发", "茶色")
MULTI = ("四位", "三名", "四人", "众人", "们围", "角色们", "并列", "排成一列", "两位少女",
         "一群人", "大家")


def from_desc(group: str) -> str:
    """画面描述里的外貌特征（发色权重高，"双马尾/短发"这类只当参考）"""
    d = A.cg_desc(group) or ""
    if not d:
        return ""
    if any(k in d for k in MULTI):
        return "共"                    # 一图里一堆人 → 算共通用
    best, score = "", 0
    for pid, kws in LOOK.items():
        s = 0
        for k in kws:
            if k in d:
                s += 3 if k in HAIR else 1      # 发色是强特征
        if s > score:
            best, score = pid, s
    return best if score >= 2 else ""


def main() -> int:
    sheet_path = A.cg_sheet_path()
    rows = []
    if os.path.isfile(sheet_path):
        rows = list(csv.reader(io.open(sheet_path, encoding="utf-8-sig")))
    head = [r for r in rows if r and r[0] in ("CG组",)]
    body = [r for r in rows if r and r[0] and r[0] not in ("CG组",) and not r[0].startswith("#")]
    known = {r[0]: (r[1] if len(r) > 1 else "") for r in body}

    todo = [g for g in sorted(A.any_cg_list()) if not A.cg_pet(g)]
    print(f"没归属的 CG：{len(todo)} 组")
    changed = 0
    for g in todo:
        who = from_context(g) or from_desc(g)
        tag = "剧本" if from_context(g) else ("描述" if who else "")
        if who and not known.get(g):
            known[g] = who
            changed += 1
            print(f"  {g:10s} → {who}（依据：{tag}）  {((A.cg_desc(g) or '')[:36])}")
        elif not who:
            print(f"  {g:10s} → 认不出来，留空（可手改）")

    # 写回（保留原有列）
    try:
        from tool.cg_owner_sheet import HEADER, HELP  # type: ignore
    except Exception:
        HEADER = ["CG组", "归属角色", "原版分类", "帧数", "说明"]
        HELP = []
    with io.open(sheet_path, "w", encoding="utf-8-sig", newline="") as fh:
        for line in HELP:
            fh.write(line + "\n")
        w = csv.writer(fh)
        w.writerow(HEADER)
        for g in sorted(A.any_cg_list()):
            pet = known.get(g, "")
            name = A.PET_NAMES.get(A.cg_pet(g) or "", "") if pet else ""
            w.writerow([g, pet, A.cg_title(g), len(A.any_cg_list().get(g) or []),
                        "自动判定：" + (name or pet or "未归属")])
    print(f"✅ 已写回 {sheet_path}（本次补了 {changed} 组）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
