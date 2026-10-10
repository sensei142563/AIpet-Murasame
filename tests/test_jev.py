# -*- coding: utf-8 -*-
"""tool/jev.py 的离线测试：不需要 TYPESAFE_API_KEY，也不访问网络。

覆盖：
  1. 无 key → available() 为假，choose()/score() 直接返回 (None, 0.0)，且不应发起任何请求
  2. 有 key + 替换 _post → 能解析答案与置信度（兼容 answers/results/outputs 多种形状）
  3. 模型给的答案**不在候选集里** → 视为失败（宁可不用也不乱用）
  4. 请求抛异常（网络错误/超时/坏 JSON）→ 退化成 (None, 0.0)，不把异常泄漏给调用方
  5. score 越界 → 失败
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool import jev  # noqa: E402


def _no_key(monkeypatch=None):
    os.environ.pop(jev.ENV_KEY, None)


def test_no_key_means_unavailable_and_no_network(monkeypatch=None):
    os.environ.pop(jev.ENV_KEY, None)
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("无 key 时不应发起请求")

    real = jev._post
    jev._post = boom
    try:
        assert jev.available({}) is False
        assert jev.choose("状态", ["a", "b"], "选哪个", cfg={}) == (None, 0.0)
        assert jev.score("状态", "打几分", cfg={}) == (None, 0.0)
        assert called["n"] == 0
    finally:
        jev._post = real


def test_with_key_parses_choice(monkeypatch=None):
    os.environ[jev.ENV_KEY] = "test-key"
    real = jev._post
    jev._post = lambda payload, key, timeout=6.0: {
        "answers": [{"answer": "哭哭", "confidence": 0.83}]
    }
    try:
        assert jev.available({}) is True
        val, conf = jev.choose("主人今天不理我", ["哭哭", "偷看你", "否定"], "配哪个表情", cfg={})
        assert val == "哭哭" and abs(conf - 0.83) < 1e-6
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


def test_parses_other_response_shapes():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    try:
        for payload in (
            {"results": [{"value": "偷看你", "score": 0.5}]},
            {"outputs": [{"choice": "偷看你", "confidence": 0.5}]},
            {"answers": [{"label": "偷看你", "confidence": 0.5}]},
        ):
            jev._post = lambda p, key, timeout=6.0, _pl=payload: _pl
            val, conf = jev.choose("s", ["偷看你", "否定"], "q", cfg={})
            assert val == "偷看你", payload
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


def test_answer_outside_options_is_rejected():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    jev._post = lambda p, key, timeout=6.0: {"answers": [{"answer": "不存在的表情", "confidence": 0.99}]}
    try:
        assert jev.choose("s", ["哭哭", "否定"], "q", cfg={}) == (None, 0.0)
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


def test_network_failure_degrades_silently():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post

    def boom(*a, **k):
        raise OSError("network down")

    jev._post = boom
    try:
        assert jev.choose("s", ["a"], "q", cfg={}) == (None, 0.0)
        assert jev.score("s", "q", cfg={}) == (None, 0.0)
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


def test_score_bounds():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    try:
        jev._post = lambda p, key, timeout=6.0: {"answers": [{"answer": "1.7", "confidence": 0.9}]}
        assert jev.score("s", "q", 0.0, 1.0, cfg={}) == (None, 0.0)
        jev._post = lambda p, key, timeout=6.0: {"answers": [{"answer": "0.42", "confidence": 0.9}]}
        v, c = jev.score("s", "q", 0.0, 1.0, cfg={})
        assert abs(v - 0.42) < 1e-6 and abs(c - 0.9) < 1e-6
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


if __name__ == "__main__":
    # 自跑兜底（没有 pytest 时也能验证）
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("   PASS " + name)
            except Exception as e:
                fails += 1
                print("   FAIL " + name + " -> " + type(e).__name__ + ": " + e)
    print("   自跑结果: %s" % ("全部通过 ✓" if fails == 0 else "%d 个失败 ✗" % fails))
    sys.exit(1 if fails else 0)
