
try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji / ⚠ 之类字符会 UnicodeEncodeError 直接打断调用方。
    # 本模块会被 .bat 用 `python -c "from tool.xxx import ..."` 直接调用 ——
    # 那条路**没有**进程入口的 stdout 守卫，所以在这里自己兜一层（幂等、只放宽编码）。
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
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


def set_key(path: str, key: str, value, create: bool = True) -> bool:
    """只改 config.json 里的**一个键**（其它键原样保留），写完原子替换。

    为什么要单独有这个：写配置这件事在仓库里被手抄过好几份，抄出来的版本有两种毛病
    （下面两种都真踩过）：
      1) `cfg = dict(get_config(p))` 然后整份 dump —— config.json **不存在**时
         get_config 返回的是 config.example.json，于是把示例里的占位值
         （sk-your-deepseek-key 这种）当成主人的设置落了盘；而且从此 config.json 存在了，
         以后再也走不到"缺失就回退示例"那条路。
      2) 写 "./config.json" 这种**相对路径**：桌宠被别的 cwd 拉起（快捷方式/计划任务/
         其它宿主）时会写到别的地方去，表现是"设置改了但不生效"。
    所以这里统一：先 ensure_config()（缺失时由示例生成一份真正的 config.json），
    再**原样读回**、只改这一个键、继承原换行风格、写 .tmp 后 os.replace 换上去。
    """
    try:
        p = os.path.abspath(path)
        if create:
            ensure_config(p)
        raw = {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
        except Exception:
            raw = _example_defaults(p)      # 真损坏时用示例兜底，至少键是齐的
        if not isinstance(raw, dict):
            raw = {}
        try:
            with open(p, "rb") as f:
                head = f.read(65536)
            nl = "\r\n" if b"\r\n" in head else "\n"
        except Exception:
            nl = "\n"
        raw[key] = value
        text = json.dumps(raw, ensure_ascii=False, indent=2)
        if nl != "\n":
            text = text.replace("\n", nl)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text + nl)
        os.replace(tmp, p)
        return True
    except Exception as e:
        _say(f"[Config] ⚠ 写 {key} 到 {path} 失败: {e}")
        return False


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
