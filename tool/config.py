
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

# 程序目录（tool/ 的上一级）。**不 import tool.paths**：本模块被 `python -c` 直接调用，
# 要保持零依赖 —— 多引一个模块就多一个把这条路弄崩的机会。
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_path(path: str) -> str:
    """把 `"./config.json"` 这种相对路径**钉到真正那份配置**上，返回绝对路径。

    为什么要有这一步：仓库里读配置的地方有 50+ 处，几乎全写 `get_config("./config.json")`，
    而"当前工作目录"并不等于程序目录：
      * 快捷方式 / 计划任务 / 别的宿主拉起 → cwd 可能是 System32、用户主目录、宿主目录
      * `python -c "from tool.xxx import ..."` 在别的目录里跑（.bat 就是这么干的）
      * 自测与探针脚本会 chdir
    那时 `"./config.json"` 指向别处：轻则**读不到**（静默退回示例默认值 → 表现为
    "设置改了不生效"），重则模块级下标访问 KeyError 直接崩 —— `tool/chat.py` 与
    `tool/cloud_API_chat.py` 是在**导入期**读的，最典型（§22 记过这个坑）。

    规则（向后兼容优先，绝不改变"正常情况"的行为）：
      1) 绝对路径 → 原样返回
      2) cwd 下**确实存在** → 用它（老行为：在自己目录里放配置照样生效）
      3) 带子目录的相对路径（`cfg/config.json`）→ **保留结构**：先试程序目录下的同结构，
         没有就按 cwd 解析。⚠ 不能拿 basename 去找程序目录的同名文件 —— 那会把
         `cfg/config.json` 悄悄变成根目录的 `config.json`（探针抓过这个错）。
      4) 光秃秃的文件名（`./config.json`）→ 程序目录下有同名文件就用它，
         谁都没有也用程序目录的路径：第一次写入落在程序目录，不散落到 cwd。
    """
    try:
        if not path:
            return path
        if os.path.isabs(path):
            return path
        if os.path.isfile(path):
            return os.path.abspath(path)
        rel_dir = os.path.dirname(path)
        if rel_dir and rel_dir not in (".", ""):
            under_app = os.path.join(APP_DIR, path.lstrip("./\\"))
            return under_app if os.path.isfile(under_app) else os.path.abspath(path)
        alt = os.path.join(APP_DIR, os.path.basename(path))
        return alt
    except Exception:
        return path


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


_missing_warned = set()


def _notice_missing_keys(path: str, cfg: dict) -> None:
    """配置文件**存在**、但少了示例里的键时，给一句可读提示（一次性，不刷屏）。

    ⚠ 以前这种情况**完全静默**：而调用方大量用 `cfg["model_type"]` 这类下标访问
      （本函数上面的 docstring 就承诺"示例配置保证这些键都在"，但那只在
      **文件缺失/损坏**时才成立）。缺键 + 下标 = KeyError + 一大段 traceback，
      用户看不懂发生了什么。实测（_audit_fish9269/repro_cfg_missing_key.py）：
      config 裁到最小时 6/6 种读取全部 KeyError。

    这里**只说清事实，不改任何值、不写文件**（不合并默认值：示例的默认值未必等于
    各功能内部的默认值，比如 qq_stt_enabled 示例是 true 而代码默认 False ，
    贸然合并会把"没配"变成"开启"）。
    """
    if not cfg or path in _missing_warned:
        return
    ex = _example_defaults(path)
    if not ex:
        return
    missing = [k for k in ex if k not in cfg]
    if not missing:
        return
    _missing_warned.add(path)
    show = "、".join(missing[:5])
    more = ("等 %d 个" % len(missing)) if len(missing) > 5 else ""
    _say("[Config] 提示：%s 里没有示例中的 %d 个键（%s%s）—— 没配的功能各自用自己的默认值；"
         "要补齐可对照 config.example.json（本提示只出现一次）"
         % (os.path.basename(path), len(missing), show, more))


def get_config(path: str) -> dict:
    """读 config.json；**文件缺失/损坏时回退到 config.example.json 的默认值**，不抛异常。

    ⚠ 以前这里是裸 `open()`：只要 config.json 不在就 `FileNotFoundError` 直接崩，
      而**绿色版/新解压目录本来就不带 config.json**（隐私设计：里面是密钥），
      于是每个入口都在第一行就死 —— 用户实测"点启动微信秒卡退"就是这个
      （`run_wechat.py` 第 249 行 `cfg = get_config("./config.json")`）。

    回退用示例配置（而不是空 dict）是故意的：调用方大量使用
    `get_config("./config.json")["model_type"]` 这种**下标访问**，返回空 dict 只会把
    FileNotFoundError 换成 KeyError，照样崩。示例配置保证这些键都在。

    ⚠ 读之前先过 `resolve_path()`：cwd 不是程序目录时（宿主/计划任务/`python -c`），
      `"./config.json"` 会指向别处 —— 那时**不是"配置缺失"而是"看错了地方"**，
      以前会静默退回示例默认值，表现为"我明明配好了却不生效"。
    """
    p = resolve_path(path)
    try:
        with open(p, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        _notice_missing_keys(p, cfg)
        return cfg
    except FileNotFoundError:
        if p not in _warned:
            _warned.add(p)
            _say(f"[Config] 未找到 {p}（绿色版首次运行还没生成？）→ "
                 f"先用 config.example.json 的默认值继续；可在启动器设置页或手工填入自己的配置。")
        return _example_defaults(p)
    except Exception as e:
        if p not in _warned:
            _warned.add(p)
            _say(f"[Config] 读取 {p} 失败（{e}）→ 用 config.example.json 的默认值继续")
        return _example_defaults(p)


def ensure_config(path: str = "./config.json") -> str:
    """首次运行：由同目录的 config.example.json 生成 config.json（已存在则**绝不覆盖**）。

    为什么要有它：README 写着"首次打开启动器会自动生成一份空白 config.json"，但代码里
    其实**没有人做这件事**（只有 install.bat 与一键安装器会生成）—— 于是"直接双击
    exe 的绿色版"里没有 config.json，微信/QQ 入口一读配置就 FileNotFoundError 秒退
    （用户实测"点启动微信秒卡退"）。这里补齐这个承诺。
    返回生成后的路径（生成失败/示例缺失时返回原 path）。
    """
    path = resolve_path(path)
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
        p = resolve_path(path)
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


_enum_warned = set()


def enum_of(value, allowed, default: str, name: str = "") -> str:
    """配置里的**枚举值**：去掉首尾空白 + 转小写后返回；不认识 → default +（一次性）可读提示。

    为什么要有它：枚举值决定**走哪条分支**。实测同一个键在仓库里有 23 处裸比、只有 4 处
    做了 .lower() —— 用户把 `model_type` 写成 `"Local"`，`api.py` 第 479 行按「本地」走、
    第 87 行按「非本地」走，**同一个进程里自相矛盾**（用户感受是"有时好使有时不好使"）；
    还有 `"local "`（尾随空格）、`"LOCAL"` 这类手写变体。

    没配（None/""）时**不提示** —— 那是"用默认值"，不是"写错了"。
    """
    s = str(value if value is not None else "").strip().lower()
    if s in allowed:
        return s
    if s and name and (name, s) not in _enum_warned:
        _enum_warned.add((name, s))
        _say("[Config] %s 的值是 %r，不在可用取值（%s）里 → 按 %r 处理；"
             "要改请在启动器设置页或 config.json 里改（本提示只出现一次）"
             % (name, value, " / ".join(allowed), default))
    return default


def num(value, default: float, lo: float = None, hi: float = None) -> float:
    """配置里的**数值**：读不懂（None/""/"abc"/列表…）就用 default，越界夹到 [lo, hi]。

    为什么要有它：用户会手改 config.json（本项目里真改过），而数值键写错有两种后果，
    都很难查：
      1) 写成 "abc" → `int()/float()` 抛异常。在**后台线程**里抛 = 线程静默死掉
         （摄像头/截图就此不再工作，界面上没有任何提示）
      2) 写成 0 或负数 → "间隔"类参数变成**忙循环**：Worker_class 里的
         `for _ in range(int(self.interval * 10)): time.sleep(0.1)` 一次都不睡 →
         满速抓帧（摄像头）/ 满速抓屏并且不停写临时 PNG（截图线程）
    返回 float（调用方需要 int 自己 int()：`int(num(cfg.get("x"), 100, 1, 86400))`）。
    """
    try:
        if isinstance(value, bool):          # True/False 不是"数值"的意思，别当 1/0
            return default
        v = float(value)
        if v != v:                           # NaN
            return default
    except (TypeError, ValueError):
        return default
    if lo is not None and v < lo:
        v = lo
    if hi is not None and v > hi:
        v = hi
    return v


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
