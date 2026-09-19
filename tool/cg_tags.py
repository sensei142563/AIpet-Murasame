# -*- coding: utf-8 -*-
"""给 CG 说明打标签（写进 _CG说明.csv 第三列）

为什么要标签：剧情里写"我们的唇贴在一起"，用关键词去匹配"相拥接吻"这种描述是对不上的；
先让模型把说明归一成固定标签（接吻/拥抱/室内/夜晚…），再拿剧情文字去对标签，就能对得准。

用法：python tool/cg_tags.py
"""
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import caption as C   # noqa: E402
from story import generator as G  # noqa: E402

BATCH = 25


def ask_tags(items: dict) -> dict:
    lines = ["%s：%s" % (k, v) for k, v in items.items()]
    user = ("下面是一组 galgame CG 的画面描述，请给每一条选 2~5 个标签。\n"
            "只能从这些标签里选：" + "、".join(C.TAGS) + "\n"
            "每条要能看出：在做什么、在哪里、什么时候。\n"
            "只输出 JSON：{\"CG编号\": [\"标签1\",\"标签2\"], ...}，不要解释。\n\n"
            + "\n".join(lines))
    txt = G._ask_model("你只输出 JSON。", user, timeout=240) or ""
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except Exception:
        d = {}
    return {k: v for k, v in (d or {}).items() if isinstance(v, list)}


def main() -> int:
    sheet = C.load_sheet()
    if not sheet:
        print("⚠ 还没有 _CG说明.csv，先跑一次「识别 CG 内容」")
        return 1
    # 说明 + 原剧本上下文一起给模型 → 标签更准（它能看到这一幕本来在演什么）
    # ⚠ 上下文只在"喂给模型"时临时拼上，**不能写回说明列**（否则会把说明污染成
    #   "…｜原剧本：…｜原剧本：…"，生成剧情时给 AI 的清单也会重复）
    try:
        import story.assets as A
        ctx_map = A.cg_context_map()
    except Exception:
        ctx_map = {}
    clean_sheet = dict(sheet)
    for k in list(sheet):
        ctx = ctx_map.get(k)
        if ctx and "｜原剧本" not in sheet[k]:
            sheet[k] = f"{sheet[k]}｜原剧本：{ctx}"
    old = C.load_tags()
    todo = {k: v for k, v in sorted(sheet.items()) if not old.get(k) or "--force" in sys.argv}
    print("共 %d 张，本次要打标签 %d 张" % (len(sheet), len(todo)))
    keys = list(todo)
    got = {}
    for i in range(0, len(keys), BATCH):
        part = {k: todo[k] for k in keys[i:i + BATCH]}
        got.update(ask_tags(part))
        print("  第 %d 批 → %d 条" % (i // BATCH + 1, len(got)))
    if not got:
        print("没拿到标签（模型没返回 JSON？）")
        return 1
    p = C.sheet_path()
    rows = [["CG组", "画面内容", "标签"]]
    for k, v in sorted(clean_sheet.items()):
        tg = got.get(k) or old.get(k) or []
        rows.append([k, v, "/".join(tg)])
    with io.open(p, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("# 每张 CG 在演什么（自动识别，可手动改）\n")
        fh.write("# 第三列=标签，用 / 分隔（接吻/拥抱/室内/夜晚…），生成剧情时按它挑图\n")
        csv.writer(fh).writerows(rows)
    print("✅ 标签已写回 %s" % p)
    for k in ("事件CG_ev303a", "事件CG_ev101a", "事件CG_ev301a"):
        print("  ", k, "→", got.get(k) or old.get(k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
