import json
import os

_warned = set()


def _say(msg: str) -> None:
    """打印提示，但**绝不因为编码问题把调用方搞崩**。

    ⚠ 教训（本次自己踩的）：这里原来写的是 `print(f"[Config] ⚠ …")` —— 而 `⚠` 不在 GBK 里，
      中文 Windows 控制台（没做 UTF-8 guard 的入口）编不出来 → `UnicodeEncodeError`
      在"回退"这条路上又抛一次，等于"安全网自己先破"。
      所以：不带非 GBK 字符 + 兜一层 try，最坏也要把话说出来。
    """
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("utf-8", "replace").decode("ascii", "replace"))
        except Exception:
            pass


def _example_defaults(path: str) -> dict:
    """同目录下的 config.example.json（示例/默认值）"""
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(path)) or ".", "config.example.json")
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def get_config(path: str) -> dict:
    """读 config.json；**文件缺失/损坏时回退到 config.example.json 的默认值**，不抛异常。

    ⚠ 以前这里是裸 `open()`：只要 config.json 不在就 `FileNotFoundError` 直接崩，
      而**绿色版/新解压目录本来就不带 config.json**（隐私设计：里面是密钥），
      于是每个入口都在第一行就死 —— 用户实测"点启动微信秒卡退"就是这个
      （`run_wechat.py` 第 249 行 `cfg = get_config("./config.json")`）。

    回退用示例配置（而不是空 dict）是故意的：调用方大量使用
    `get_config("./config.json")["model_type"]` 这种**下标访问**，返回空 dict 只会把
    FileNotFoundError 换成 KeyError，照样崩。示例配置保证这些键都在。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if path not in _warned:
            _warned.add(path)
            _say(f"[Config] 未找到 {path}（绿色版首次运行还没生成？）→ "
                 f"先用 config.example.json 的默认值继续；可在启动器设置页或手工填入自己的配置。")
        return _example_defaults(path)
    except Exception as e:
        if path not in _warned:
            _warned.add(path)
            _say(f"[Config] 读取 {path} 失败（{e}）→ 用 config.example.json 的默认值继续")
        return _example_defaults(path)


def ensure_config(path: str = "./config.json") -> str:
    """首次运行：由同目录的 config.example.json 生成 config.json（已存在则**绝不覆盖**）。

    为什么要有它：README 写着"首次打开启动器会自动生成一份空白 config.json"，但代码里
    其实**没有人做这件事**（只有 install.bat 与一键安装器会生成）—— 于是"直接双击
    exe 的绿色版"里没有 config.json，微信/QQ 入口一读配置就 FileNotFoundError 秒退
    （用户实测"点启动微信秒卡退"）。这里补齐这个承诺。
    返回生成后的路径（生成失败/示例缺失时返回原 path）。
    """
    try:
        if os.path.isfile(path):
            return path
        src = os.path.join(os.path.dirname(os.path.abspath(path)) or ".", "config.example.json")
        if not os.path.isfile(src):
            return path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        import shutil
        shutil.copy2(src, path)
        _say(f"[Config] 首次运行：已由 config.example.json 生成 {os.path.basename(path)}"
             f"（空白默认值，请在启动器设置页填入自己的 API Key / QQ 号等）")
    except Exception as e:
        _say(f"[Config] 生成 {path} 失败（继续用示例默认值）: {e}")
    return path


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
