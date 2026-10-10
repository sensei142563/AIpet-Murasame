"""Jev（TypeSafe "System One"）薄客户端 —— 只用于**封闭、可验证、高频**的判断节点。

报文形状**照官方 API 规格**（docs.typesafe.ai/api，2026-10 抓取）：

    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <API_KEY>
    {
      "model": "jev-latest",
      "state": <string | object | array>,          # 被判断的内容
      "questions": {                               # ★ 映射（map），不是数组
         "<key>": { "type": "choice", "instructions": "...",
                    "criteria": { "<选项>": "<描述>" } },   # 每个 choice 最多 255 个选项
         "<key2>": { "type": "score", "instructions": "...", "criteria": { ... } }
      }
    }

答案按**同一个 key** 返回；choice/score 额外带 confidence（0~1，由概率分布推导）。
错误码：401 = key 无效；422 = body 校验失败（例如缺 instructions/criteria）。

为什么单独做一层：
- Jev 不生成文本，只回答带类型的问题；适合"挑哪个表情包""这句是什么情绪""要不要联网"这类
  封闭选择题，**不适合**写文案/总结/解释理由（那些仍应交给大语言模型）。
- 官方是**云端 API**，且对部分地区返回 HTTP 451；因此本层的实现必须**可替换**：
  调用方只认 choose()/score()/yes_no()，将来换成**本地开源复现**（如 NanoJev，0.6B）时，
  把 _post 换成"本地推理"即可，调用点一行都不用改。

设计约束（刻意为之）：
1. **零新依赖**：只用标准库 urllib。
2. **绝不抛异常**：任何失败退化成 (None, 0.0)。
3. **答案必须落在候选集里**：否则视为失败（宁可不用，也不乱用）。
4. **无 key 时一个请求都不发**：调用方按"没有判断"处理，行为与以前一致。
5. **_post 可替换**：测试不需要网络与 key。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

__all__ = ["DEFAULT_API_URL", "API_URL", "DEFAULT_MODEL", "ENV_KEY", "ENV_BASE", "ENV_MODEL",
           "endpoint", "api_key", "model_id", "available", "choose", "score", "yes_no"]

DEFAULT_API_URL = "https://api.typesafe.ai/v1/systemone"
API_URL = DEFAULT_API_URL          # 兼容旧引用；实际请求用 endpoint()
DEFAULT_MODEL = "jev-latest"

ENV_KEY = "TYPESAFE_API_KEY"
ENV_BASE = "TYPESAFE_BASE_URL"     # 可选：代理/自建网关（区域被 451 拦时用）
ENV_MODEL = "TYPESAFE_MODEL"       # 可选：覆盖模型 id

DEFAULT_TIMEOUT = 6.0
MAX_CHOICES = 255                  # 官方限制：每个 choice 最多 255 个选项


def endpoint() -> str:
    """实际请求地址：默认官方；设了 TYPESAFE_BASE_URL 则用它（代理/自建网关）。"""
    v = (os.environ.get(ENV_BASE) or "").strip()
    return v if v else DEFAULT_API_URL


def model_id() -> str:
    v = (os.environ.get(ENV_MODEL) or "").strip()
    return v if v else DEFAULT_MODEL


def api_key(cfg=None) -> str:
    """取 API key：环境变量优先，其次项目配置。取不到返回空串。"""
    k = (os.environ.get(ENV_KEY) or "").strip()
    if k:
        return k
    if isinstance(cfg, dict):
        v = cfg.get("typesafe_api_key")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def available(cfg=None) -> bool:
    """是否具备调用条件（有 key）。**不联网**。"""
    return bool(api_key(cfg))


def _post(payload: dict, key: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """真正发请求。失败抛异常，由上层统一兜住。测试里会被替换。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint(),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "Bearer " + key,
            "User-Agent": "AIpet-Murasame/jev-client",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip() else {}


def _ask(state, questions: dict, cfg=None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """按官方规格组包并请求；返回原始响应（失败/不可用 → {}）。"""
    key = api_key(cfg)
    if not key or not questions or state is None or (isinstance(state, str) and not state.strip()):
        return {}
    payload = {"model": model_id(), "state": state, "questions": questions}
    try:
        return _post(payload, key, timeout) or {}
    except Exception:
        return {}


def _answers_map(data) -> dict:
    """把响应稳妥地归一成 {key: answer_dict}。

    兼容几种可能形状：
      {"answers": {"k": {...}}} / {"answers": [{"key": ..., ...}]} / {"results": ...} / {"outputs": ...}
    """
    if not isinstance(data, dict):
        return {}
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


def _value_conf(ans: dict):
    """从一个答案对象里取 (值, 置信度)。"""
    if not isinstance(ans, dict):
        return (ans if isinstance(ans, str) else None), 0.0
    val = ans.get("answer", ans.get("value", ans.get("choice", ans.get("label"))))
    if isinstance(val, dict):
        val = val.get("choice", val.get("value", val.get("label")))
    conf = ans.get("confidence", ans.get("score", 0.0))
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    return (val if isinstance(val, (str, int, float)) else None), conf


def _first(ans_map: dict, keys):
    """按待选 key 列表取第一个命中的答案对象。"""
    for k in keys:
        if k in ans_map:
            return ans_map[k]
    if len(ans_map) == 1:                      # 只有一个答案时，不管 key 名
        return next(iter(ans_map.values()))
    return None


def choose(state, options, instructions: str, cfg=None, timeout: float = DEFAULT_TIMEOUT,
           qkey: str = "pick"):
    """从候选里选一个。返回 (选项, 置信度)；失败/候选外 → (None, 0.0)。"""
    opts = [str(o) for o in (options or [])][:MAX_CHOICES]
    if not opts:
        return None, 0.0
    questions = {qkey: {"type": "choice", "instructions": instructions,
                        "criteria": {o: "" for o in opts}}}
    ans = _first(_answers_map(_ask(state, questions, cfg, timeout)), [qkey])
    if ans is None:
        return None, 0.0
    val, conf = _value_conf(ans)
    if val is None or str(val) not in opts:
        return None, 0.0
    return str(val), conf


def score(state, instructions: str, levels, cfg=None, timeout: float = DEFAULT_TIMEOUT,
          qkey: str = "score"):
    """在给定等级上打分（官方 score 类型），返回 (值, 置信度)；失败 → (None, 0.0)。"""
    lv = [str(x) for x in (levels or [])]
    if not lv:
        return None, 0.0
    questions = {qkey: {"type": "score", "instructions": instructions,
                        "criteria": {x: "" for x in lv}}}
    ans = _first(_answers_map(_ask(state, questions, cfg, timeout)), [qkey])
    if ans is None:
        return None, 0.0
    val, conf = _value_conf(ans)
    if val is None:
        return None, 0.0
    return val, conf


def yes_no(state, instructions: str, cfg=None, timeout: float = DEFAULT_TIMEOUT):
    """布尔判断，返回 ("yes"/"no"/None, 置信度)。"""
    return choose(state, ["yes", "no"], instructions, cfg=cfg, timeout=timeout, qkey="yn")
