# -*- coding: utf-8 -*-
"""从解包剧本（.ks.scn，PSB 容器）里抽出每张 CG 出现时的**原剧本上下文**

剧本里的对白是 UTF-8 明文（同一句通常有 日文/简体/繁体 三个版本），
按字节位置就能抓到某个 ev 编号前后在说什么 —— 这是"这张 CG 在演什么"
最权威的依据（比视觉识别还准，因为它直接告诉你剧情）。

输出：剧情素材/CG/_CG剧本上下文.csv（CG组, 剧本上下文）
用法：python tool/cg_script_ctx.py
"""
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import assets as A  # noqa: E402

SRC = r"D:\下载\AI桌宠\新建文件夹"
SCN_DIRS = [os.path.join(SRC, "06_剧本脚本", "patch"),
            os.path.join(SRC, "06_剧本脚本", "patch_extra"),
            os.path.join(SRC, "06_剧本脚本", "data", "main"),
            os.path.join(SRC, "06_剧本脚本", "data", "scenario")]
TEXT_RE = re.compile("[\u3000-\u30ff\u4e00-\u9fff\uff00-\uffef]{4,}".encode("utf-8"))
EV_RE = re.compile(rb"ev\d{3}[a-z]?")
SD_RE = re.compile(rb"[Ss][Dd]\d{3}[A-Za-z]{0,2}")
# 成人向 CG 在剧本里是 h311 / h311a 这种写法
H_RE = re.compile(rb"[Hh]\d{3}[a-z]?")
# 繁体特征字：有简体同款句子时优先保留简体
TRAD = "們說個這來對後東視頻點個還邊時說話裡讓给為與"


def scn_files():
    out = []
    for d in SCN_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".scn", ".ks")):
                out.append(os.path.join(d, f))
    return out


def looks_simplified(s: str) -> bool:
    return not any(c in TRAD for c in s)


def scan_file(path: str, window: int = 9000) -> dict:
    """{ev编号: [对白…]}（同一文件内）"""
    try:
        b = io.open(path, "rb").read()
    except Exception:
        return {}
    runs = [(m.start(), m.group(0).decode("utf-8", "ignore")) for m in TEXT_RE.finditer(b)]
    if not runs:
        return {}
    out = {}
    for m in EV_RE.finditer(b):
        ev = m.group(0).decode("ascii")
        lo, hi = m.start() - window, m.start() + window
        near = [s for (o, s) in runs if lo <= o <= hi]
        out.setdefault(ev, []).extend(near)
    for m in SD_RE.finditer(b):                 # SD 图：SD001AA/SD001 → 归到 SD001
        key = m.group(0).decode("ascii").upper()[:5]
        lo, hi = m.start() - window, m.start() + window
        near = [s for (o, s) in runs if lo <= o <= hi]
        out.setdefault(key, []).extend(near)
    for m in H_RE.finditer(b):                  # 成人向：h311 / h311a
        key = m.group(0).decode("ascii").lower()
        lo, hi = m.start() - window, m.start() + window
        near = [s for (o, s) in runs if lo <= o <= hi]
        out.setdefault(key, []).extend(near)
        out.setdefault("h" + key[1:4], []).extend(near)   # 也记一份 h311
    return out


UI_STOP = ("アイキャッチ", "カットイン", "回想枠", "ムラサメ", "丛雨丸", "叢雨丸", "セーブ",
           "ロード", "タイトル", "メニュー", "背景", "立ち絵", "ＢＧＭ", "BGM", "SE")


def clean(lines: list, keep: int = 3) -> str:
    """去重、优先简体、挑最像对白的几句（把 UI 标签之类的噪声压掉）"""
    seen, out = set(), []
    for s in lines:
        s = s.strip("「」 \t\r\n")
        if len(s) < 6 or s in seen:
            continue
        if re.fullmatch(r"[.・…—\-—\s]+", s):
            continue
        seen.add(s)
        out.append(s)

    def score(s: str) -> int:
        sc = 0
        if re.search("[\u3040-\u30ff]", s):      # 有假名 = 日文原文
            sc -= 3
        if looks_simplified(s):
            sc += 2
        if any(c in s for c in "。，！？……、"):
            sc += 2
        if len(s) >= 10:
            sc += 1
        if any(u in s for u in UI_STOP):
            sc -= 4
        if s.startswith("——") or s.startswith("——"):
            sc -= 1
        return sc

    ranked = sorted(range(len(out)), key=lambda i: (-score(out[i]), i))
    pick = [out[i] for i in ranked[:keep]]
    pick.sort(key=lambda s: out.index(s))
    return " / ".join(pick)[:200]


def main() -> int:
    groups = sorted((A.any_cg_list() or {}).keys())
    if not groups:
        print("⚠ 没找到 CG 列表")
        return 1
    print("CG 组 %d 个，开始扫剧本…" % len(groups))
    by_ev = {}
    files = scn_files()
    for i, f in enumerate(files, 1):
        got = scan_file(f)
        for ev, lines in got.items():
            by_ev.setdefault(ev, []).extend(lines)
        if got:
            print("  [%d/%d] %s → %d 个 CG 编号" % (i, len(files), os.path.basename(f)[:34], len(got)))
    print("剧本里一共提到 %d 个 CG 编号" % len(by_ev))

    rows, hit = [], 0
    for g in groups:
        ctx = ""
        m = re.search(r"(ev\d+[a-z]?)", g)
        if m:
            ev = m.group(1)
            # 只认**一模一样**的编号：ev702a 的上下文不能塞给 ev701a/ev703a，
            # 否则一堆不相关的 CG 拿到同一段剧本，配图判断全乱。
            if ev in by_ev:
                ctx = clean(by_ev[ev])
        if not ctx and g.upper().startswith("SD"):
            key = g.upper()[:5]                 # SD001
            if key in by_ev:
                ctx = clean(by_ev[key])
        if not ctx and g.startswith("成人"):
            # 成人向 CG：剧本里写作 h311 / h311a
            m2 = re.search(r"ev(\d{3})", g)
            if m2:
                n = m2.group(1)
                for cand in ("h" + n + "a", "h" + n, "h" + n.lstrip("0")):
                    if cand in by_ev:
                        ctx = clean(by_ev[cand])
                        break
        if ctx:
            hit += 1
        rows.append([g, ctx])

    p = os.path.join(A.cg_root() or os.path.join(A.BASE, "剧情素材", "CG"), "_CG剧本上下文.csv")
    with io.open(p, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("# 每张 CG 出现时原剧本里前后的对白（从解包剧本 .ks.scn 里抽的）\n")
        w = csv.writer(fh)
        w.writerow(["CG组", "剧本上下文"])
        w.writerows(rows)
    print("✅ 写出 %s" % p)
    print("   有上下文的 %d/%d 张" % (hit, len(rows)))
    for g, c in rows[:6]:
        print("   %-22s %s" % (g, (c or "(无)")[:70]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
