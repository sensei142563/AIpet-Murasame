# -*- coding: utf-8 -*-
"""任务经验：把她"做成过的事"记下来，下次直接照做。

为什么要有
----------
以前每次让她开软件都是从零规划（明明上次已经成功过）。现在每完成一个任务，就把
"任务关键词 → 这次怎么做的"存一份；下次接到类似任务，先把这条经验放进提示里 ——
又快又不容易跑偏。失败的也记（fail 计数），避免重复踩同一个坑。

存储：`pets/<角色>/memory/experience.json`（**本地文件**，里面会存任务文字，注意隐私）
    { "打开哔哩哔哩": {"task": "帮我把哔哩哔哩打开",
                      "steps": ["由 dsh 完成", "打开了 bilibili 首页"],
                      "ok": 3, "fail": 1, "ts": 1730000000} }

在本仓库里怎么用（与 agent 桥接形成闭环，见 classes/Worker_class.py 的 AgentWorker）
-------------------------------------------------------------------------------
    · 跑之前：`note_for(task)` → 找到旧经验就作为提示塞进交给 agent 的任务里
    · 跑完：`learn(task, steps, ok)` → 成功记 ok+1（并更新 steps），失败记 fail+1
上限：最多 60 条（按时间留最新的）；开关：config.json → experience_enabled（默认 true）
"""
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAX_ITEMS = 60
MAX_STEPS = 10
_budget = {"day": "", "n": 0}          # 预留：将来若要限制"每天最多学几条"用得上


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def enabled() -> bool:
    try:
        from tool.config import get_config, as_bool
        return as_bool(get_config("./config.json").get("experience_enabled", "true"), True)
    except Exception:
        return True


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
        os.replace(tmp, p)              # 原子替换
    except Exception as e:
        _say("[经验] ⚠ 保存失败: %s" % e)


def _key(task: str) -> str:
    """任务关键词：去掉客套话，只留动作与对象"""
    t = re.sub(r"\s+", "", str(task or ""))
    t = re.sub(r"^(帮我|请|麻烦|给我|替我|你能不能|你能|可以|帮忙)", "", t)
    t = re.sub(r"(吧|好吗|好不好|一下|呗|谢谢|呗呗)$", "", t)
    return t[:24]


def _keywords(text: str) -> list:
    """英文词 + 中文二字组（粗粒度关键词，够用且不依赖分词库）"""
    out = []
    try:
        for m in re.finditer(r"[A-Za-z]{2,}", str(text or "")):
            out.append(m.group(0).lower())
        zh = re.sub(r"[^\u4e00-\u9fff]", "", str(text or ""))
        for i in range(len(zh) - 1):
            out.append(zh[i:i + 2])
    except Exception:
        pass
    return out[:30]


def learn(task: str, steps: list, ok: bool = True):
    """记一次经验：任务 → 这次怎么做的（成功才更新 steps；失败只累加 fail）"""
    try:
        if not enabled():
            return
        k = _key(task)
        if not k or not steps:
            return
        steps = [str(s)[:60] for s in steps if str(s).strip()][:MAX_STEPS]
        if not steps:
            return
        d = _load()
        cur = dict(d.get(k) or {})
        if ok:
            cur["steps"] = steps
            cur["ok"] = int(cur.get("ok") or 0) + 1
        else:
            cur["fail"] = int(cur.get("fail") or 0) + 1
            if not cur.get("steps"):
                cur["steps"] = []          # 失败但还没成功过 → 不当作可复用经验
        cur["ts"] = time.time()
        cur["task"] = str(task)[:60]
        d[k] = cur
        _save(d)
        if ok:
            _say("[经验] 记下：%s → %s" % (k, " / ".join(steps[:4])))
    except Exception as e:
        _say("[经验] ⚠ 记录失败: %s" % e)


def find(task: str) -> dict:
    """找最匹配的经验（关键词重合度最高、且成功过的）"""
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
            if int(item.get("ok") or 0) <= 0:      # 只失败过的，不当经验用
                continue
            ks = set(_keywords(key))
            inter = len(kws & ks)
            if not inter:
                continue
            sc = inter + (2.0 if k == key else 0.0) + min(3, int(item.get("ok") or 0)) * 0.3
            if sc > best_sc:
                best_sc, best = sc, item
        return best
    except Exception:
        return {}


def note_for(task: str) -> str:
    """给模型/agent 的提示（有旧经验才返回内容）"""
    try:
        it = find(task)
        if not it:
            return ""
        steps = " → ".join(str(s) for s in (it.get("steps") or [])[:6])
        return ("【你以前这样做过（成功 %d 次，优先照做）】%s。如果情况不一样再自己判断。"
                % (int(it.get("ok") or 0), steps))
    except Exception:
        return ""


def summary_text(limit: int = 8) -> str:
    """给人看的一页（状态窗"经验"页用）"""
    d = _load()
    items = sorted(d.items(), key=lambda kv: -float((kv[1] or {}).get("ts") or 0))[:limit]
    if not items:
        return "（还没有经验记录）"
    out = []
    for k, it in items:
        steps = " → ".join(str(x) for x in (it.get("steps") or [])[:6])
        out.append("· %s（成功 %s 次%s）：%s"
                   % (k, it.get("ok") or 0,
                      ("，失败 %s 次" % it.get("fail")) if it.get("fail") else "", steps))
    return "\n".join(out)


def clear_cache():
    """换角色/测试用（本模块不缓存，留个同名接口方便统一调用）"""
    return None


if __name__ == "__main__":
    _say("开关: %s" % enabled())
    _say("存储: %s" % _path())
    _say("")
    _say("模拟记两条经验：")
    learn("帮我把哔哩哔哩打开", ["由 dsh 完成", "打开了 bilibili 首页"], True)
    learn("帮我打开网易云音乐", ["由 codex 完成", "启动了网易云音乐"], True)
    _say("")
    _say("查「打开哔哩哔哩」的经验：")
    _say("  %s" % (find("打开哔哩哔哩") or "（没找到）"))
    _say("  提示词：%s" % note_for("帮我把哔哩哔哩打开"))
    _say("")
    _say(summary_text())
