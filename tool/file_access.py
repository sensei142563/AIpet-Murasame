# -*- coding: utf-8 -*-
"""让桌宠能看看电脑里的文件和文件夹（只读，不写不改不删）。

开关（默认关闭）：桌宠右键菜单 →「允许读取电脑文件」→ config.json 的 file_access_enabled。

她怎么用（和【看屏幕】同一个套路，回复里带一行标记就行）：
    【文件】列出 桌面              看桌面上有什么（桌面 / 文档 / 下载 / 图片 / 音乐 / 视频）
    【文件】列出 D:\\下载           看指定目录里的东西
    【文件】读 D:\\下载\\笔记.txt    看看某个文本文件里写了什么
    【文件】找 报告                 在允许的目录里按文件名找东西
标记那一行不会念出来，也不会显示在对话框；桌宠会真的去翻，然后把内容交给她接着聊。

安全边界（重要）：
    * 只读：不写、不改、不删、不移动
    * 只允许"用户目录 + 桌面/文档/下载/图片/音乐/视频 + 桌宠自己的目录"
    * 系统目录一律拒绝（Windows、Program Files、AppData、System32、ProgramData…）
    * 单文件最多 200KB、最多 4000 字；每次最多列 60 条；每轮最多处理 1 个请求
    * 每次读取都写一行日志（data/file_access.log），随时能查她翻了什么
"""
import os
import re
import time

MAX_FILE_BYTES = 200 * 1024
MAX_CHARS = 4000
MAX_LIST = 60
MAX_FIND = 30
FILE_MARK = "【文件】"
_LOG = os.path.join("data", "file_access.log")

# 桌面/文档 这类别名 → 真实路径（用 Windows 的已知文件夹，避免中文用户名出错）
_ALIASES = {
    "桌面": "Desktop", "文档": "Documents", "下载": "Downloads",
    "图片": "Pictures", "音乐": "Music", "视频": "Videos",
    "desktop": "Desktop", "documents": "Documents", "downloads": "Downloads",
    "pictures": "Pictures", "music": "Music", "videos": "Videos",
}
# 一律拒绝的系统目录（小写前缀匹配）
_BLOCKED = (
    "c:\\windows", "c:\\program files", "c:\\program files (x86)", "c:\\programdata",
    "c:\\$recycle.bin", "c:\\perflogs", "c:\\system volume information",
    "c:\\users\\administrator\\appdata", "appdata\\local", "appdata\\roaming",
    "\\windows\\system32", "\\windows\\syswow64",
)
# 不读的文件类型（二进制/媒体/压缩包，读了也是乱码）
_SKIP_EXT = (
    ".exe", ".dll", ".sys", ".bin", ".dat", ".db", ".sqlite", ".pyc", ".pyd", ".so", ".dylib",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".xz", ".iso", ".cab",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".svg",
    ".mp3", ".wav", ".flac", ".ape", ".m4a", ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv",
    ".ttf", ".otf", ".woff", ".woff2", ".onnx", ".pt", ".pth", ".safetensors", ".gguf",
    ".psd", ".ai", ".blend", ".pak", ".assets",
)
# 需要读的文本类后缀（白名单优先，避免把 .log/.md 之类漏掉）
_TEXT_EXT = (".txt", ".md", ".markdown", ".log", ".json", ".jsonl", ".csv", ".tsv", ".ini",
             ".cfg", ".conf", ".yaml", ".yml", ".toml", ".xml", ".html", ".htm", ".css",
             ".js", ".ts", ".py", ".pyw", ".java", ".c", ".h", ".cpp", ".cs", ".go", ".rs",
             ".bat", ".cmd", ".ps1", ".sh", ".sql", ".env", ".properties", ".gitignore", "")

# 名字里带这些词的，一律不读也不列内容（怕她念出密码、密钥之类）
_SENSITIVE = ("密码", "password", "passwd", "账号", "账户", "account", "密钥", "secret",
              "token", "cookie", "credential", "身份证", "银行卡", "信用卡", "私钥",
              "id_rsa", ".pem", ".key", ".pfx", "wallet", "助记词", "seed")

# 一轮的待处理请求（Worker 解析到标记时放进来，主线程取走执行）
_pending = [None]


def _cfg_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def _log(msg: str):
    try:
        print(f"[文件] {msg}")
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(_LOG) or ".", exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def enabled() -> bool:
    """是否允许读取电脑文件（config.json 的 file_access_enabled，默认关闭）"""
    try:
        from tool.config import get_config
        v = get_config("./config.json").get("file_access_enabled", "false")
        return str(v).strip().lower() in ("true", "1", "yes", "on")
    except Exception:
        return False


def set_enabled(on: bool) -> bool:
    try:
        from tool.config import get_config
        import json
        cfg = dict(get_config("./config.json") or {})
        cfg["file_access_enabled"] = "true" if on else "false"
        p = _cfg_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        _log(f"读取电脑文件 → {'已开启' if on else '已关闭'}")
        return True
    except Exception as e:
        _log(f"开关写入失败:{e}")
        return False


def prompt_rules() -> str:
    """交给模型的能力说明（开启时才注入）"""
    if not enabled():
        return ""
    return (
        "【看电脑里的文件（已开启）】你可以看看主人电脑里的文件（只读，不会改动任何东西）。"
        "需要的时候，在回复里单独写一行：\n"
        "【文件】列出 桌面（也可以写 文档／下载／图片／音乐／视频，或者完整路径如 D:\\下载）\n"
        "【文件】读 D:\\下载\\笔记.txt（看看某个文本文件里写了什么）\n"
        "【文件】找 简历（按文件名找东西）\n"
        "标记那一行不会被念出来，主人也不会看到；桌宠会真的去翻，然后把内容交给你接着说。\n"
        "★ 主人问「我桌面上有什么」「那个文件里写了啥」这类问题时就这么做——别猜、别编，"
        "看到什么就说什么。看不见的（比如系统目录、图片内容）就直说看不到。\n"
        "★ 只读得到，写不了也删不了；每次只能看一个地方，看完再说话。"
    )


# ─────────────────────── 解析 / 暂存 / 清理 ───────────────────────

_LINE = re.compile("[【\\[]\\s*文件\\s*[】\\]]\\s*([^\"\\]\\n]{1,200})")


def _parse_one(raw: str):
    """把「列出 桌面」解析成 (动作, 参数)"""
    s = str(raw or "").strip().strip("：:，,。")
    if not s:
        return None
    for kw, kind in (("列出", "list"), ("看看", "list"), ("显示", "list"), ("list", "list"),
                     ("读", "read"), ("打开", "read"), ("看看内容", "read"), ("cat", "read"),
                     ("找", "find"), ("搜索", "find"), ("查找", "find"), ("find", "find")):
        if s.startswith(kw):
            arg = s[len(kw):].strip().strip("：:，,。\"'「」")
            return (kind, arg) if arg else None
    # 只给了一个路径 → 当"列出"
    return ("read" if os.path.splitext(s)[1] else "list", s)


def parse(text: str) -> list:
    out = []
    for m in _LINE.finditer(str(text or "")):
        got = _parse_one(m.group(1))
        if got:
            out.append(got)
    return out[:1]           # 一轮只做一件事，别让她一口气翻一堆


def clean_for_speech(text: str) -> str:
    """把标记行从要说出口的文字里去掉（标记只剩标记本身，主线程还要用它触发）"""
    src = str(text or "")
    try:
        if not _LINE.search(src):
            return src
        return _LINE.sub("", src).strip()
    except Exception:
        return src


def set_pending(text: str):
    """记下这一轮的请求（Worker 解析到标记时调用）"""
    _pending[0] = (str(text or ""), time.time())


def take_pending():
    """主线程取走请求（取完就清空，避免重复执行）"""
    v = _pending[0]
    _pending[0] = None
    return v


# ─────────────────────── 路径与安全 ───────────────────────

def _user_dirs():
    """桌面/文档/下载…的真实路径（拿不到就退回 ~ 下的同名目录）"""
    out = {}
    home = os.path.expanduser("~")
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(260)
        for name, csidl in (("Desktop", 0), ("Documents", 5), ("Downloads", 0x0009),
                            ("Pictures", 39), ("Music", 13), ("Videos", 14)):
            try:
                if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0 and buf.value:
                    out[name] = buf.value
            except Exception:
                pass
    except Exception:
        pass
    for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"):
        out.setdefault(name, os.path.join(home, name))
    out["Home"] = home
    out["_root"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 桌宠自己的目录
    return out


def resolve(raw: str):
    """把「桌面」「D:\\下载」解析成真实路径；不合法/越界返回 (None, 原因)"""
    s = str(raw or "").strip().strip('"\'')
    if not s:
        return None, "没说要找哪儿"
    dirs = _user_dirs()
    low = s.lower()
    # 别名
    if s in _ALIASES:
        return dirs.get(_ALIASES[s]) or dirs["Home"], ""
    if low in ("我的电脑", "此电脑", "home", "~", "用户目录"):
        return dirs["Home"], ""
    if low in ("桌宠目录", "你自己的目录", "项目目录"):
        return dirs["_root"], ""
    # 只有名字、没有盘符 → 当桌面上/文档里的名字
    if not re.match(r"^[a-zA-Z]:", s) and not s.startswith("\\\\") and not s.startswith("\\"):
        for base in (dirs.get("Desktop"), dirs.get("Documents"), dirs.get("Downloads"), dirs["_root"]):
            if not base:
                continue
            cand = os.path.join(base, s)
            if os.path.exists(cand):
                return os.path.abspath(cand), ""
        return None, f"没找到「{s}」（我只能看桌面、文档、下载这些地方）"
    p = os.path.abspath(os.path.expandvars(os.path.expanduser(s)))
    lp = p.lower()
    for b in _BLOCKED:                     # 先判系统目录，再判存在性（不然只会说"路径不存在"）
        if lp.startswith(b) or b in lp:
            return None, "系统目录我不能翻（怕影响你电脑）"
    if not os.path.exists(p):
        return None, f"路径不存在：{p}"
    return p, ""


def _too_big(path: str):
    try:
        return os.path.getsize(path) > MAX_FILE_BYTES
    except Exception:
        return True


def _is_text(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in _SKIP_EXT:
        return False
    return True


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f%s" % (n, unit) if unit == "B" else "%.1f%s" % (n, unit)
        n /= 1024.0
    return "%.1fGB" % n


def _list_dir(path: str) -> str:
    try:
        names = os.listdir(path)
    except Exception as e:
        return f"打不开这个文件夹（{type(e).__name__}）"
    dirs_, files_ = [], []
    for n in names:
        if n.startswith("$") or n == "desktop.ini":
            continue
        full = os.path.join(path, n)
        if os.path.isdir(full):
            dirs_.append(n)
        else:
            try:
                files_.append((n, os.path.getsize(full), os.path.getmtime(full)))
            except Exception:
                files_.append((n, 0, 0))
    files_.sort(key=lambda x: -x[2])
    head = f"目录 {path} 里共有 {len(dirs_)} 个文件夹、{len(files_)} 个文件。"
    lines = []
    if dirs_:
        lines.append("文件夹：" + "、".join(dirs_[:20]))
    if files_:
        items = []
        for n, sz, mt in files_[:MAX_LIST]:
            items.append("%s（%s，%s）" % (n, _fmt_size(sz),
                                        time.strftime("%m-%d %H:%M", time.localtime(mt))))
        lines.append("文件（按最近修改排序，最多 60 个）：" + "；".join(items))
    return head + "\n" + "\n".join(lines)


def _read_file(path: str) -> str:
    if os.path.isdir(path):
        return _list_dir(path)
    low = os.path.basename(path).lower()
    for w in _SENSITIVE:
        if w in low:
            _log(f"拒绝读取敏感文件：{path}")
            return "这个文件名字看着像密码/密钥之类的，我不看（看了也不该说出口）"
    if not _is_text(path):
        return f"{os.path.basename(path)} 是二进制/媒体文件，看不到里面的内容（只能看文本类文件）"
    if _too_big(path):
        return f"{os.path.basename(path)} 太大了（超过 200KB），读出来会用光我的脑子"
    data = None
    for enc in ("utf-8", "utf-8-sig", "gbk", "big5", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                data = f.read(MAX_CHARS * 2)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"读不了这个文件（{type(e).__name__}）"
    if data is None:
        return "这个文件编码怪怪的，读出来是乱码"
    total = ""
    try:
        total = f"（文件共 {_fmt_size(os.path.getsize(path))}，下面是最多前 {MAX_CHARS} 字）"
    except Exception:
        pass
    body = data[:MAX_CHARS]
    if len(data) > MAX_CHARS:
        body += "\n……（后面还有，先看这些）"
    return f"{os.path.basename(path)} {total}：\n{body}"


def _find(name: str) -> str:
    if not name:
        return "要找什么？"
    hits = []
    dirs = _user_dirs()
    for base in (dirs.get("Desktop"), dirs.get("Documents"), dirs.get("Downloads"),
                 dirs.get("Pictures"), dirs.get("Music"), dirs.get("Videos"), dirs["_root"]):
        if not base or not os.path.isdir(base):
            continue
        try:
            for root, subdirs, files in os.walk(base):
                subdirs[:] = [d for d in subdirs if d not in
                              (".git", "node_modules", "__pycache__", "runtime", "_internal")]
                for n in files + subdirs:
                    if name.lower() in n.lower():
                        hits.append(os.path.join(root, n))
                        if len(hits) >= MAX_FIND:
                            break
                if len(hits) >= MAX_FIND:
                    break
        except Exception:
            continue
        if len(hits) >= MAX_FIND:
            break
    if not hits:
        return f"在桌面、文档、下载这些地方都没找到名字里有「{name}」的东西"
    return f"名字里有「{name}」的大概有这些（最多 {MAX_FIND} 个）：\n" + "\n".join(hits)


def run(requests=None) -> str:
    """执行一轮请求，返回给她看的文本（永远返回一句人话，不抛异常）"""
    if not enabled():
        return ""
    reqs = requests if requests is not None else ([take_pending()[0]] if _pending[0] else [])
    if isinstance(reqs, str):
        reqs = [reqs]
    for raw in (reqs or [])[:1]:
        # ⚠ 要取标记后面的那截（捕获组），不能把整个匹配删掉——那样连"列出 桌面"一起没了
        m = _LINE.search(str(raw))
        arg_text = m.group(1) if m else str(raw)
        got = _parse_one(arg_text)
        if not got:
            return "我没看懂要做什么（可以写「【文件】列出 桌面」这样）"
        kind, arg = got
        path, err = resolve(arg)
        _log(f"{kind} {arg!r} → {'拒绝: ' + err if err else path}")
        if err:
            return err
        try:
            if kind == "list":
                return _list_dir(path)
            if kind == "read":
                return _read_file(path)
            return _find(arg)
        except Exception as e:
            return f"看的时候出了点问题（{type(e).__name__}）"
    return ""


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("开关:", enabled())
    print("说明长度:", len(prompt_rules()))
    print()
    print("=== 解析 ===")
    for d in ("【文件】列出 桌面", "【文件】读 D:\\下载\\测试.txt", "【文件】找 报告",
              "【文件】看看下载", "[文件] list desktop"):
        print("  %-34s → %s" % (d, parse(d)))
    print()
    print("=== 安全 ===")
    for p in ("C:\\Windows\\System32", "C:\\Program Files\\QQ", "C:\\Users\\Administrator\\AppData\\Roaming",
              "桌面", "D:\\不存在的目录xyz"):
        print("  %-46s → %s" % (p, resolve(p)))
    print()
    print("=== 真读一次桌面 ===")
    print(_list_dir(resolve("桌面")[0])[:400])
