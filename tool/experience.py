# -*- coding: utf-8 -*-
"""任务经验：把她"做成过的事"记下来，下次直接照做（参考 AgentPet 的经验沉淀）。

以前每次让她开软件都是从零规划（明明上次已经成功过）。
现在每完成一个任务，就把"任务关键词 → 成功用的动作序列"存一份；
下次接到类似任务，直接把这条经验放进规划提示里 —— 又快又不容易跑偏。

存储：pets/<角色>/memory/experience.json
     { "打开哔哩哔哩": {"steps": ["按组合键 win", "输入文字「bilibili」", "按键 enter"],
                      "ok": 3, "fail": 1, "ts": 1730000000} }
"""
import json
import os
import re
import time

MAX_ITEMS = 60
_budget = {"day": "", "n": 0}


def _path() -> str:
    try:
        from pets.pet_registry import get_memory_dir
        d = get_memory_dir()
    except Exception:
        d = "memory"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "experience.json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict):
    try:
        items = sorted(d.items(), key=lambda kv: -float((kv[1] or {}).get("ts") or 0))
        d = dict(items[:MAX_ITEMS])
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception as e:
        print(f"[经验] ⚠ 保存失败: {e}")


def _key(task: str) -> str:
    """任务关键词：去掉客套话，只留动作与对象"""
    t = re.sub("\\s+", "", str(task or ""))
    t = re.sub("^(帮我|请|麻烦|给我|替我|你能不能|你能|可以|帮忙)", "", t)
    t = re.sub("(吧|好吗|好不好|一下|呗|谢谢|呗呗)$", "", t)
    return t[:24]


def _keywords(text: str) -> list:
    out = []
    try:
        for m in re.finditer("[A-Za-z]{2,}", text):
            out.append(m.group(0).lower())
        zh = re.sub("[^\\u4e00-\\u9fff]", "", text)
        for i in range(len(zh) - 1):
            out.append(zh[i:i + 2])
    except Exception:
        pass
    return out[:30]


def learn(task: str, steps: list, ok: bool = True):
    """记一次经验：任务 → 这次用的动作序列（成功才算数）"""
    try:
        k = _key(task)
        if not k or not steps:
            return
        steps = [str(s)[:60] for s in steps if str(s).strip()][:10]
        if not steps:
            return
        d = _load()
        cur = dict(d.get(k) or {})
        if ok:
            cur["steps"] = steps
            cur["ok"] = int(cur.get("ok") or 0) + 1
        else:
            cur["fail"] = int(cur.get("fail") or 0) + 1
        cur["ts"] = time.time()
        cur["task"] = str(task)[:60]
        d[k] = cur
        _save(d)
        if ok:
            print(f"[经验] 记下：{k} → {' / '.join(steps[:4])}")
    except Exception as e:
        print(f"[经验] ⚠ 记录失败: {e}")


def find(task: str) -> dict:
    """找最匹配的经验（关键词重合度最高且成功过的）"""
    try:
        k = _key(task)
        if not k:
            return {}
        d = _load()
        kws = set(_keywords(k))
        best, best_sc = {}, 0.0
        for key, item in d.items():
            if not isinstance(item, dict) or not item.get("steps"):
                continue
            if int(item.get("ok") or 0) <= 0:
                continue
            ks = set(_keywords(key))
            inter = len(kws & ks)
            if not inter:
                continue
            sc = inter + (2.0 if k == key else 0.0) + min(3, int(item.get("ok") or 0)) * 0.3
            if sc > best_sc:
                best, best_sc = item, sc
        return best if best_sc >= 2 else {}
    except Exception:
        return {}


def note_for(task: str) -> str:
    """给规划提示用的一行：以前这样做过"""
    it = find(task)
    if not it:
        return ""
    steps = " → ".join(str(s) for s in (it.get("steps") or [])[:6])
    return (f"【你以前这样做过（成功 {int(it.get('ok') or 0)} 次，优先照做）】{steps}。"
            f"如果情况不一样再自己判断。")


def summary_text(limit: int = 8) -> str:
    d = _load()
    items = sorted(d.items(), key=lambda kv: -float((kv[1] or {}).get("ts") or 0))[:limit]
    if not items:
        return "（还没有经验记录）"
    out = []
    for k, it in items:
        out.append("· %s（成功 %s 次）：%s" % (k, it.get("ok"), " → ".join(str(x) for x in (it.get("steps") or [])[:4])))
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("存储:", _path())
    print()
    print("模拟记两条经验：")
    learn("帮我把哔哩哔哩打开", ["按组合键 win", "输入文字「bilibili」", "按键 enter", "等待"], True)
    learn("帮我打开网易云音乐", ["按组合键 win", "输入文字「网易云」", "按键 enter"], True)
    print()
    print("查「打开哔哩哔哩」的经验：")
    print("  ", find("打开哔哩哔哩") or "（没找到）")
    print("  提示词：", note_for("帮我把哔哩哔哩打开"))
    print()
    print(summary_text())
