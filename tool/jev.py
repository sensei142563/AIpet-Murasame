"""Jev 判断层薄客户端 —— **双契约**，可指向云端或本地。

支持两种后端（按 endpoint 自动识别，调用方无感）：

  1) 云端 TypeSafe "System One"（官方规格，docs.typesafe.ai/api）
     POST https://api.typesafe.ai/v1/systemone     Authorization: Bearer <API_KEY>
     { "model": "jev-latest", "state": <str|obj|arr>,
       "questions": { "<qid>": { "type": "choice"|"score"|"boolean",
                                 "instructions": "...", "criteria": {...} } } }

  2) 本地开源复现 **NanoJev**（0.6B；scripts/predict_toy_decisions.py:validate_request 为准确契约）
     POST http://127.0.0.1:8765/api/evaluate
     { "states": [ { "id": "<唯一>", "state": <str|obj|arr>,
                     "questions": { "<qid>": { "type": "choice"|"score"|"boolean",
                                               "instructions": "...", "criteria": ... } } } ] }
     硬约束：choice 的 criteria 是 **dict（2–255）且键值都必须非空字符串**；
             score 的 criteria 是 **有序数组（2–10）**；boolean 的 criteria 可选（仅 false/true）；
             顶层**只能有 states**（多一个键就报错）。

识别方式：endpoint 里含 "/api/evaluate" → 本地 NanoJev 形状；否则官方形状。
本地模式**不需要 API key**（available() 只看"有没有 key 或有没有配本地地址"）。

为什么做成这样：调用点（电脑端 QQ 侧、api.py 的 /jev/choose、安卓 JevClient）只认
choose()/score()/yes_no()，换后端只需改一个环境变量 TYPESAFE_BASE_URL，一行调用点都不用动。

设计约束（沿用至今）：
  1) 零新依赖（仅标准库 urllib）
  2) 绝不抛异常：任何失败退化成 (None, 0.0)
  3) 答案必须落在候选集里，否则视为失败（宁可不用，也不乱用）
  4) 没配 key 且没配本地地址时**一个请求都不发**
  5) _post 可替换 → 测试不需要网络与 key
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

__all__ = ["DEFAULT_API_URL", "API_URL", "DEFAULT_MODEL", "ENV_KEY", "ENV_BASE", "ENV_MODEL",
           "endpoint", "is_local", "api_key", "model_id", "available",
           "choose", "score", "yes_no"]

DEFAULT_API_URL = "https://api.typesafe.ai/v1/systemone"
API_URL = DEFAULT_API_URL          # 兼容旧引用；实际请求用 endpoint()
DEFAULT_MODEL = "jev-latest"

ENV_KEY = "TYPESAFE_API_KEY"
ENV_BASE = "TYPESAFE_BASE_URL"     # 代理/自建网关/**本地 NanoJev 服务**都走这个
ENV_MODEL = "TYPESAFE_MODEL"       # 仅云端用

DEFAULT_TIMEOUT = 6.0
LOCAL_TIMEOUT = 120.0              # 本地 CPU 推理慢，给足时间
MAX_CHOICES = 255


def endpoint() -> str:
    v = (os.environ.get(ENV_BASE) or "").strip()
    return v if v else DEFAULT_API_URL


def is_local() -> bool:
    """指到本地 NanoJev 服务？（它只认 /api/evaluate 这个路径）"""
    return "/api/evaluate" in endpoint()


def model_id() -> str:
    v = (os.environ.get(ENV_MODEL) or "").strip()
    return v if v else DEFAULT_MODEL


def api_key(cfg=None) -> str:
    k = (os.environ.get(ENV_KEY) or "").strip()
    if k:
        return k
    if isinstance(cfg, dict):
        v = cfg.get("typesafe_api_key")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def available(cfg=None) -> bool:
    """能发请求吗：本地地址存在（无需 key）**或**有 key。不联网。"""
    return bool(api_key(cfg)) or (is_local() and endpoint().startswith("http"))


def _post(payload: dict, key: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8",
               "User-Agent": "AIpet-Murasame/jev-client"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(endpoint(), data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip() else {}


def _ask(state, qid: str, question: dict, cfg=None, timeout=None) -> dict:
    """按当前 endpoint 组包并请求；返回**归一化后**的若干答案形状（失败 → {}）。"""
    key = api_key(cfg)
    if not available(cfg):
        return {}
    if state is None or (isinstance(state, str) and not state.strip()):
        return {}
    local = is_local()
    if timeout is None:
        timeout = LOCAL_TIMEOUT if local else DEFAULT_TIMEOUT
    try:
        if local:
            payload = {"states": [{"id": "s1", "state": state, "questions": {qid: question}}]}
        else:
            payload = {"model": model_id(), "state": state, "questions": {qid: question}}
        return _post(payload, key, timeout) or {}
    except Exception:
        return {}


def _answers_map(data) -> dict:
    """把两种后端的响应都归一成 {qid: answer}。

    云端可能：{"answers": {"q": {...}}} / {"answers": [{...}]} / {"results": ...} / {"outputs": ...}
    本地则为：{"states": [{"id": "s1", "answers": {"q": ...}}]}
    """
    if not isinstance(data, dict):
        return {}
    # 本地 NanoJev
    if isinstance(data.get("states"), list):
        out = {}
        for st in data["states"]:
            if not isinstance(st, dict):
                continue
            ans = st.get("answers")
            if isinstance(ans, dict):
                for k, v in ans.items():
                    out[str(k)] = v if isinstance(v, dict) else {"value": v}
        return out
    raw = data.get("answers")
    if raw is None:
        raw = data.get("results")
    if raw is None:
        raw = data.get("outputs")
    if raw is None:
        return {}
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[str(k)] = v if isinstance(v, dict) else {"value": v}
        return out
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            k = item.get("key", item.get("id", item.get("name", item.get("question"))))
            if k is None and len(raw) == 1:
                k = "__one__"
            if k is not None:
                out[str(k)] = item
    return out


def _value_conf(ans):
    """从答案对象里取 (值, 置信度)。兼容 value/answer/choice/label 与 chosen/choice_id。"""
    if not isinstance(ans, dict):
        return (ans if isinstance(ans, (str, int, float)) else None), 0.0
    val = ans.get("answer", ans.get("value", ans.get("choice", ans.get("label"))))
    if val is None:
        val = ans.get("chosen", ans.get("choice_id", ans.get("selection")))
    if isinstance(val, dict):
        val = val.get("choice", val.get("value", val.get("label"), val.get("id")))
    # 置信度：优先显式字段；没有就用"被选中那一项的概率"（本地 NanoJev 实测就是这种形状）
    conf = None
    for _k in ("confidence", "score", "probability"):
        if _k in ans and ans[_k] is not None:
            conf = ans[_k]
            break
    if conf is None:
        probs = ans.get("probabilities") or ans.get("distribution")
        if isinstance(probs, dict) and val is not None:
            conf = probs.get(str(val), 0.0)
        else:
            conf = 0.0
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    return (val if isinstance(val, (str, int, float)) else None), conf


def _first(ans_map: dict, keys):
    for k in keys:
        if k in ans_map:
            return ans_map[k]
    if len(ans_map) == 1:
        return next(iter(ans_map.values()))
    return None


def _criteria_choice(options):
    """choice 的 criteria：dict（键=候选名，值=描述）。**值必须非空**（NanoJev 硬约束）。"""
    return {str(o): ("配「%s」的选项" % o) for o in options}


def choose(state, options, instructions: str, cfg=None, timeout=None, qkey: str = "pick"):
    """从候选里选一个。返回 (选项, 置信度)；失败/候选外 → (None, 0.0)。"""
    opts = [str(o) for o in (options or [])][:MAX_CHOICES]
    if not opts:
        return None, 0.0
    q = {"type": "choice", "instructions": instructions, "criteria": _criteria_choice(opts)}
    ans = _first(_answers_map(_ask(state, qkey, q, cfg, timeout)), [qkey])
    if ans is None:
        return None, 0.0
    val, conf = _value_conf(ans)
    if val is None or str(val) not in opts:
        return None, 0.0
    return str(val), conf


def score(state, instructions: str, levels, cfg=None, timeout=None, qkey: str = "score"):
    """在给定等级上打分。**criteria 用有序数组**（NanoJev 硬约束）。返回 (值, 置信度)。"""
    lv = [str(x) for x in (levels or [])]
    if not lv:
        return None, 0.0
    # 后端形状不同：本地 NanoJev 的 score 要**有序数组**；云端官方要**映射**（等级 → 说明）
    if is_local():
        criteria = lv
    else:
        criteria = {x: ("等级「%s」" % x) for x in lv}
    q = {"type": "score", "instructions": instructions, "criteria": criteria}
    ans = _first(_answers_map(_ask(state, qkey, q, cfg, timeout)), [qkey])
    if ans is None:
        return None, 0.0
    val, conf = _value_conf(ans)
    if val is None:
        return None, 0.0
    return val, conf


def yes_no(state, instructions: str, cfg=None, timeout=None, qkey: str = "yn"):
    """布尔判断。云端用 choice(yes/no)，本地用 boolean（同样接受 yes/no 两种写法）。"""
    local = is_local()
    if local:
        q = {"type": "boolean", "instructions": instructions,
             "criteria": {"true": "是", "false": "否"}}
        ans = _first(_answers_map(_ask(state, qkey, q, cfg, timeout)), [qkey])
        if ans is None:
            return None, 0.0
        # 实测形状里常常只给 probabilities（没有 value/choice）→ 先按 true/false 比大小
        probs = ans.get("probabilities") if isinstance(ans, dict) else None
        if isinstance(probs, dict) and probs:
            def _num(x):
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return 0.0
            t = _num(probs.get("true", probs.get("yes", 0.0)))
            f = _num(probs.get("false", probs.get("no", 0.0)))
            return ("yes" if t >= f else "no"), (t if t >= f else f)
        val, conf = _value_conf(ans)
        if val is None:
            return None, 0.0
        s = str(val).strip().lower()
        if s in ("true", "yes", "1", "是"):
            return "yes", conf
        if s in ("false", "no", "0", "否"):
            return "no", conf
        # 分布形态：比较 true/false 哪边大
        probs = ans.get("probabilities") if isinstance(ans, dict) else None
        if isinstance(probs, dict) and probs:
            try:
                t = float(probs.get("true", probs.get("yes", 0.0)))
                f = float(probs.get("false", probs.get("no", 0.0)))
                return ("yes" if t >= f else "no"), (t if t >= f else f)
            except (TypeError, ValueError):
                pass
        return None, 0.0
    return choose(state, ["yes", "no"], instructions, cfg=cfg, timeout=timeout, qkey=qkey)
