"""Jev（TypeSafe "System One"）薄客户端 —— 只用于**封闭、可验证、高频**的判断节点。

为什么单独做一层：
- Jev 不生成文本，它只回答**带类型的问题**（从给定选项里选一个 / 在量表上打分 / 给出 0~1 概率），
  并附带置信度，官方称 70–500ms。所以它适合"挑哪个表情包""这句是什么情绪""要不要联网"这类
  选择题，**不适合**写文案/总结/解释理由（那些仍应交给大语言模型）。
- 官方是**云端 API**：POST https://api.typesafe.ai/v1/systemone，需要 TYPESAFE_API_KEY。
  因此本模块的全部设计前提是：**没有 key 也能正常工作**（available() 为假，调用方走原有逻辑）。

设计约束（刻意为之）：
1. **零新依赖**：只用标准库 urllib.request（打包/离线环境友好）。
2. **绝不抛异常**：任何失败都退化成 (None, 0.0)，调用方按"没有判断"处理。
3. **答案必须落在候选集里**：模型返回的字符串若不在候选中，视为失败（宁可不用，也不乱用）。
4. **可离线自测**：_post 可被替换（monkeypatch），因此测试不需要网络与 key。

用法：
    from tool.jev import available, choose
    if available(cfg):
        name, conf = choose(state=最近对话, options=表情包文件名列表,
                            question="这句回复最该配哪个表情包？", cfg=cfg)
        if name and conf >= 0.5:
            send_sticker(name)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

__all__ = ["API_URL", "api_key", "available", "choose", "score", "yes_no"]

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_TIMEOUT = 6.0
# 环境变量优先，其次项目配置（config.json 里的 typesafe_api_key）
ENV_KEY = "TYPESAFE_API_KEY"
CFG_KEY = "typesafe_api_key"


def api_key(cfg=None) -> str:
    """取 API key：环境变量优先，其次项目配置。取不到返回空串。"""
    k = (os.environ.get(ENV_KEY) or "").strip()
    if k:
        return k
    if isinstance(cfg, dict):
        v = cfg.get(CFG_KEY)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def available(cfg=None) -> bool:
    """是否具备调用条件（有 key）。**不联网**，因此可以随便调。"""
    return bool(api_key(cfg))


def _post(payload: dict, key: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """真正发请求。失败抛异常，由上层统一兜住。测试里会被替换掉。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
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


def _ask(state: str, question: str, kind: str, options=None, cfg=None,
         timeout: float = DEFAULT_TIMEOUT) -> dict:
    """统一入口，返回 {} 表示不可用/失败。"""
    key = api_key(cfg)
    if not key or not isinstance(state, str) or not state.strip():
        return {}
    q: dict = {"kind": kind, "question": question}
    if kind == "choice":
        q["options"] = list(options or [])
        if not q["options"]:
            return {}
    payload = {"state": state, "questions": [q]}
    try:
        return _post(payload, key, timeout) or {}
    except Exception:
        return {}


def _first_answer(data: dict):
    """从响应里稳妥地取第一个答案（官方结构可能微调，这里对多种形状都兼容）。"""
    if not isinstance(data, dict):
        return None, 0.0
    ans = data.get("answers") or data.get("results") or data.get("outputs") or []
    if isinstance(ans, dict):
        ans = [ans]
    if not ans:
        return None, 0.0
    a = ans[0]
    if not isinstance(a, dict):
        return (a if isinstance(a, str) else None), 0.0
    val = a.get("answer", a.get("value", a.get("choice", a.get("label"))))
    conf = a.get("confidence", a.get("score", 0.0))
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    if isinstance(val, dict):          # 形如 {"choice": "xxx"}
        val = val.get("choice", val.get("value", val.get("label")))
    return (val if isinstance(val, str) else None), conf


def choose(state: str, options, question: str, cfg=None, timeout: float = DEFAULT_TIMEOUT):
    """从候选里选一个。

    返回 (选项, 置信度)；不可用/失败/答案不在候选里 → (None, 0.0)。
    """
    opts = [str(o) for o in (options or [])]
    data = _ask(state, question, "choice", options=opts, cfg=cfg, timeout=timeout)
    val, conf = _first_answer(data)
    if val is not None and val not in opts:
        return None, 0.0          # 宁可不用，也不乱用
    return val, conf


def score(state: str, question: str, lo: float = 0.0, hi: float = 1.0,
          cfg=None, timeout: float = DEFAULT_TIMEOUT):
    """在量表上打分，返回 (分数, 置信度)；失败 → (None, 0.0)。"""
    data = _ask(state, question, "score", cfg=cfg, timeout=timeout)
    val, conf = _first_answer(data)
    if val is None:
        return None, conf
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None, 0.0
    if f < lo or f > hi:
        return None, 0.0
    return f, conf


def yes_no(state: str, question: str, cfg=None, timeout: float = DEFAULT_TIMEOUT):
    """布尔判断，返回 (True/False/None, 置信度)。"""
    return choose(state, ["yes", "no"], question, cfg=cfg, timeout=timeout)
