# -*- coding: utf-8 -*-
"""让视觉模型按"人物特征对照表"判断每张 CG 里是谁，写回 _CG归属表.csv

为什么：解包的 cglist.csv 只给到"芳01/茉01/…/共01"这种组级标签，
共01 里的图有些其实是某位女主的单人图（例如 ev703a 是茉子的忍者图），
光看"哪个剧本文件引用了它"会误判 —— 直接看图里是谁最准。

用法：python tool/cg_ask_who.py [组名 …]（不给就用内置清单）
"""
import base64
import io
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from story import assets as A          # noqa: E402
from story import caption as C         # noqa: E402

ROSTER = """这是《千恋＊万花》的一张 CG。请对照下面的人物特征，判断画面里主要出现的是谁：
- 丛雨：浅绿色（浅绿松石色）长发、绿瞳，性格古灵精怪，常拿着刀（丛雨丸）
- 芳乃：银白色长发、蓝眼睛，巫女，穿红白和服或巫女服
- 茉子：黑色头发，忍者，用苦无／短刀，护卫打扮
- 蕾娜：金色（亚麻色）双马尾、紫眼睛，外国人，常穿和风洋装
- 小春：粉色头发（短发或挽起），和果子店／甜品屋的店员，系围裙
- 芦花：深红棕色长发，年长的姐姐，经营甜品茶屋
如果画面里是两位以上角色，或只是男主角／风景，就回答「多人」或「都不是」。
只输出一行：角色名（丛雨／芳乃／茉子／蕾娜／小春／芦花／多人／都不是）+ 一句话依据。"""

CACHE = "_CG角色识别.json"
ALIAS = {"丛雨": "murasame", "芳乃": "fano", "茉子": "mako", "蕾娜": "rena",
         "小春": "koharu", "芦花": "roka", "ムラサメ": "murasame", "ム": "murasame"}

DEFAULT = ([f"SD{i:03d}" for i in list(range(1, 15)) + list(range(101, 105)) +
            list(range(201, 205)) + [301, 401, 402, 501, 502, 503, 504]] +
           ["事件CG_ev701a", "事件CG_ev701b", "事件CG_ev702a", "事件CG_ev703a",
            "事件CG_ev302a", "事件CG_ev101a"])


def cache_path() -> str:
    return os.path.join(A.cg_root() or os.path.join(A.BASE, "剧情素材", "CG"), CACHE)


def load_cache() -> dict:
    p = cache_path()
    if os.path.isfile(p):
        try:
            return json.load(io.open(p, encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(d: dict) -> None:
    io.open(cache_path(), "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))


def frame_of(g: str) -> str:
    full = ((A.cg_index().get(g) or {}).get("full") or [])
    full = [f for f in full if f[2] >= 400] or full
    if not full:
        return ""
    big = max(full, key=lambda f: f[1] * f[2])
    return big[0]


def ask(path: str, key: str) -> str:
    with io.open(path, "rb") as fh:
        raw = fh.read()
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.width > C.MAX_SIDE:
            im = im.resize((C.MAX_SIDE, max(1, int(im.height * C.MAX_SIDE / im.width))))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        raw = buf.getvalue()
    except Exception:
        pass
    body = {"model": C.VISION_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": ROSTER},
                {"type": "image_url",
                 "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(raw).decode()}}]}],
            "max_tokens": 120}
    r = requests.post(C.URL_QWEN, json=body, headers={"Authorization": "Bearer " + key}, timeout=120)
    d = r.json()
    if r.status_code != 200:
        raise RuntimeError("HTTP %s %s" % (r.status_code, str(d)[:120]))
    return str((d.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()


def main(argv) -> int:
    groups = argv[1:] or DEFAULT
    key = ""
    try:
        from story import modelcfg
        key = str((modelcfg.load_config().get("APIKEY") or {}).get("qwen") or "").strip()
        if not key:
            key = str((modelcfg.get_short_cfg() or {}).get("api_key") or "")
    except Exception as e:
        print("⚠ 读配置失败：", e)
    if not key:
        print("⚠ 配置里没有 Qwen 的 API Key（视觉识别要用它）")
        return 1
    cache = load_cache()
    for g in groups:
        if g in cache:
            print("  %-18s (缓存) %s" % (g, cache[g].get("who")))
            continue
        p = frame_of(g)
        if not p:
            print("  %-18s 没有可用帧" % g)
            continue
        try:
            ans = ask(p, key)
        except Exception as e:
            print("  %-18s ⚠ %s" % (g, str(e)[:80]))
            continue
        who = ""
        for nm, pid in ALIAS.items():
            if ans.startswith(nm) or (nm in ans[:12]):
                who = pid
                break
        if not who and ("多人" in ans[:12] or "都不是" in ans[:12]):
            who = "共"
        cache[g] = {"who": who, "ans": ans, "file": os.path.basename(p)}
        print("  %-18s → %-8s %s" % (g, who or "?", ans[:56].replace("\n", " ")))
        save_cache(cache)
    print("✅ 识别结果缓存在", cache_path())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
