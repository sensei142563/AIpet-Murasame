# -*- coding: utf-8 -*-
"""api.py 的 /jev/choose 逻辑测试：不需要网络、不需要 key、不需要起服务。

覆盖：
  1. 路由已注册
  2. 无 key → name=None（reason=no key），且**不发起请求**
  3. state/options 缺失 → name=None
  4. 有 key + 替换 _post → 正常返回 name/confidence
  5. 候选外答案 → name=None（沿用 tool.jev 的严格性）
  6. 任何异常都被吞掉 → name=None（手机端永远拿到可解析的 JSON）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api  # noqa: E402
from tool import jev  # noqa: E402


def test_route_registered():
    paths = [getattr(r, "path", "") for r in api.app.routes]
    assert "/jev/choose" in paths, paths


def test_no_key_no_request():
    os.environ.pop(jev.ENV_KEY, None)
    called = {"n": 0}
    real = jev._post
    jev._post = lambda *a, **k: (called.__setitem__("n", called["n"] + 1), {})[1]
    try:
        out = api.jev_choose_sync("状态", ["a", "b"], "选哪个")
        assert out["name"] is None and out["reason"] == "no key"
        assert called["n"] == 0
    finally:
        jev._post = real


def test_missing_inputs():
    out = api.jev_choose_sync("", ["a"], "q")
    assert out["name"] is None
    out = api.jev_choose_sync("s", [], "q")
    assert out["name"] is None


def test_with_key_ok():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    jev._post = lambda p, key, timeout=6.0: {"answers": [{"answer": "偷看你", "confidence": 0.66}]}
    try:
        out = api.jev_choose_sync("主人回来了", ["哭哭", "偷看你"], "配哪个表情")
        assert out["name"] == "偷看你" and abs(out["confidence"] - 0.66) < 1e-6
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


def test_outside_options_rejected():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post
    jev._post = lambda p, key, timeout=6.0: {"answers": [{"answer": "不存在的", "confidence": 0.99}]}
    try:
        assert api.jev_choose_sync("s", ["a", "b"], "q")["name"] is None
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


def test_exception_is_swallowed():
    os.environ[jev.ENV_KEY] = "k"
    real = jev._post

    def boom(*a, **k):
        raise RuntimeError("boom")

    jev._post = boom
    try:
        out = api.jev_choose_sync("s", ["a"], "q")
        # tool.jev.choose 自身就吞掉异常并返回 (None, 0.0)，
        # 因此 api 层拿到的是"没有答案"而不是异常 —— 这正是我们要的：手机端永远拿到可解析的 JSON。
        assert out["name"] is None and out["confidence"] == 0.0
    finally:
        jev._post = real
        os.environ.pop(jev.ENV_KEY, None)


if __name__ == "__main__":
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
