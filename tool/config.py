import json


def get_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def as_bool(value, default: bool = False) -> bool:
    """配置里的「真值」判定：1/true/yes/y/on/开/开启 → True，其余 → False。

    config.json 里布尔值是字符串（"true"/"false"），而且历史上写法不统一
    （有 "1"、有 "on"、有中文"开"）。这段判断在仓库里被抄了 6 份
    （run.py / qq_bridge / qq_learn / touch_areas / Worker_class / build_launcher），
    这里放一份权威实现，其余逐步替换过来。
    缺省 / 空串 → default（缺省值由调用方给，避免"没配=关"把默认开的功能关掉）。
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if not s:
        return default
    return s in ("1", "true", "yes", "y", "on", "开", "开启")
