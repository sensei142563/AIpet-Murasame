# -*- coding: utf-8 -*-
"""tool/jev.py 的离线测试：不需要 TYPESAFE_API_KEY，也不访问网络。

本轮重点：**校验请求形状符合官方规格** ——
  payload = {"model": "jev-latest", "state": ..., "questions": {k: {type, instructions, criteria}}}
以及解析、严格性、静默降级。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool import jev  # noqa: E402


def _clean():
    for k in (jev.ENV_KEY, jev.ENV_BASE, jev.ENV_MODEL):
        os.environ.pop(k, None)


def test_no_key_means_unavailable_and_no_network():
    _clean()
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("无 key 时不应发起请求")

    real = jev._post
    jev._post = boom
    try:
        assert jev.available({}) is False
        assert jev.choose("状态", ["a", "b"], "选哪个", cfg={}) == (None, 0.0)
        assert jev.score("状态", "打几分", ["1", "2"], cfg={}) == (None, 0.0)
        assert called["n"] == 0
    finally:
        jev._post = real


def test_request_shape_matches_official_spec():
    """★ 本轮核心：报文必须是 model + state + questions(映射) + type/instructions/criteria。"""
    _clean()
    os.environ[jev.ENV_KEY] = "test-key"
    seen = {}

    def fake_post(payload, key, timeout=6.0):
        seen["payload"] = payload
        seen["key"] = key
        return {"answers": {"pick": {"answer": "哭哭", "confidence": 0.83}}}

    real = jev._post
    jev._post = fake_post
    try:
        val, conf = jev.choose("主人今天不理我", ["哭哭", "偷看你"], "配哪个表情", cfg={})
        p = seen["payload"]
        assert seen["key"] == "test-key"
        assert p["model"] == "jev-latest"
        assert p["state"] == "主人今天不理我"
        assert isinstance(p["questions"], dict) and "pick" in p["questions"]
        q = p["questions"]["pick"]
        assert q["type"] == "choice"
        assert q["instructions"] == "配哪个表情"
        assert isinstance(q["criteria"], dict)
        assert set(q["criteria"].keys()) == {"哭哭", "偷看你"}
        assert val == "哭哭" and abs(conf - 0.83) < 1e-6
    finally:
        jev._post = real
        _clean()


def test_model_and_base_overridable():
    _clean()
    assert jev.endpoint() == jev.DEFAULT_API_URL
    assert jev.model_id() == jev.DEFAULT_MODEL
    os.environ[jev.ENV_BASE] = "https://my-proxy.example/v1/systemone"
    os.environ[jev.ENV_MODEL] = "jev-1.13"
    seen = {}
    os.environ[jev.ENV_KEY] = "k"

    def fake_post(payload, key, timeout=6.0):
        seen["url"] = jev.endpoint()
        seen["model"] = payload["model"]
        return {"answers": {"pick": {"answer": "a", "confidence": 0.5}}}

    real = jev._post
    jev._post = fake_post
    try:
        assert jev.endpoint() == "https://my-proxy.example/v1/systemone"
        assert jev.model_id() == "jev-1.13"
        jev.choose("s", ["a"], "q", cfg={})
        assert seen["url"].startswith("https://my-proxy.example")
        assert seen["model"] == "jev-1.13"
    finally:
        jev._post = real
        _clean()


def test_parses_answer_list_and_other_shapes():
    _clean()
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    try:
        for payload in (
            {"answers": {"pick": {"value": "偷看你", "score": 0.5}}},
            {"answers": [{"key": "pick", "choice": "偷看你", "confidence": 0.5}]},
            {"results": {"pick": {"label": "偷看你", "confidence": 0.5}}},
            {"outputs": [{"id": "pick", "answer": "偷看你", "confidence": 0.5}]},
        ):
            jev._post = lambda p, key, timeout=6.0, _pl=payload: _pl
            val, conf = jev.choose("s", ["偷看你", "否定"], "q", cfg={})
            assert val == "偷看你", payload
    finally:
        jev._post = real
        _clean()


def test_answer_outside_options_is_rejected():
    _clean()
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    jev._post = lambda p, key, timeout=6.0: {"answers": {"pick": {"answer": "不存在", "confidence": 0.99}}}
    try:
        assert jev.choose("s", ["哭哭", "否定"], "q", cfg={}) == (None, 0.0)
    finally:
        jev._post = real
        _clean()


def test_network_failure_degrades_silently():
    _clean()
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post

    def boom(*a, **k):
        raise OSError("network down")

    jev._post = boom
    try:
        assert jev.choose("s", ["a"], "q", cfg={}) == (None, 0.0)
        assert jev.score("s", "q", ["1"], cfg={}) == (None, 0.0)
        assert jev.yes_no("s", "q", cfg={}) == (None, 0.0)
    finally:
        jev._post = real
        _clean()


def test_score_uses_score_type_and_returns_level():
    _clean()
    os.environ[jev.ENV_KEY] = "k"
    seen = {}

    def fake_post(payload, key, timeout=6.0):
        seen["q"] = payload["questions"]["score"]
        return {"answers": {"score": {"answer": "高", "confidence": 0.7}}}

    real = jev._post
    jev._post = fake_post
    try:
        v, c = jev.score("s", "有多烦？", ["低", "中", "高"], cfg={})
        assert seen["q"]["type"] == "score"
        assert set(seen["q"]["criteria"].keys()) == {"低", "中", "高"}
        assert v == "高" and abs(c - 0.7) < 1e-6
    finally:
        jev._post = real
        _clean()


def test_yes_no_uses_two_options():
    _clean()
    os.environ[jev.ENV_KEY] = "k"
    seen = {}
    jev._post = lambda p, key, timeout=6.0: (seen.update(q=p["questions"]["yn"]),
                                             {"answers": {"yn": {"answer": "no", "confidence": 0.6}}})[1]
    try:
        v, c = jev.yes_no("s", "要不要联网？", cfg={})
        assert set(seen["q"]["criteria"].keys()) == {"yes", "no"}
        assert v == "no"
    finally:
        jev._post = jev._post  # noqa
        _clean()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("   PASS " + name)
            except Exception as e:
                fails += 1
                print("   FAIL " + name + " -> " + type(e).__name__ + ": " + str(e)[:90])
    print("   自跑结果: %s" % ("全部通过 ✓" if fails == 0 else "%d 个失败 ✗" % fails))
    sys.exit(1 if fails else 0)
